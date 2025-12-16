from django.core.exceptions import FieldDoesNotExist
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import DatabaseError, ProgrammingError
from django.db.models import Q, Avg, Count, Sum
from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse
from django.utils.translation import get_language


import hmac
import hashlib
import json
import os
import logging
from typing import Optional
from datetime import timedelta

from .forms import ContactForm, CustomUserCreationForm, ReviewForm
from .models import (
    Category,
    Course,
    Enrollment,
    InstructorProfile,
    Lesson,
    BlockProgress,
    Payment,
    Review,
    Wishlist,
    Article,
    Material,
    UserProfile,
    Module,
    LessonBlock,
    Quiz, Question, Answer, Assignment, Submission, Certificate,
    Lead, Interaction, Segment, SupportTicket, FAQ,
    Plan, Subscription, Refund, Mailing,
    CourseStaff, AuditLog
)

# Настройка логгера
logger = logging.getLogger(__name__)

# ---------- helpers ----------

def _has_field(model, name: str) -> bool:
    """Безопасная проверка наличия поля в модели"""
    try:
        model._meta.get_field(name)
        return True
    except FieldDoesNotExist:
        return False

def public_storage_url(path: Optional[str]) -> Optional[str]:
    """Генерация публичного URL для Supabase Storage"""
    if not path:
        return None
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    bucket = os.environ.get("SUPABASE_BUCKET", "media").strip("/")
    if not base:
        base = "https://pyttzlcuxyfkhrwggrwi.supabase.co"
    return f"{base}/storage/v1/object/public/{bucket}/{path.lstrip('/')}"

def first_nonempty(*vals):
    """Возвращает первое непустое значение"""
    for v in vals:
        if v:
            return v
    return None

# ---------- webhooks/payments ----------

@csrf_exempt
def kaspi_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=400)

    signature = request.headers.get("X-Kaspi-Signature") or ""
    body = request.body
    secret = getattr(settings, "KASPI_SECRET", None)
    if not secret:
        return JsonResponse({"error": "KASPI_SECRET is not set"}, status=500)

    expected_signature = hmac.new(key=secret.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
    if signature != expected_signature:
        return JsonResponse({"error": "Invalid signature"}, status=403)

    try:
        data = json.loads(body)
        invoice_id = data.get("invoiceId")
        status = data.get("status")
        amount = data.get("amount")
        payment = Payment.objects.get(kaspi_invoice_id=invoice_id)
    except (Payment.DoesNotExist, json.JSONDecodeError, KeyError, TypeError):
        return JsonResponse({"error": "Payment not found or invalid data"}, status=404)

    # валидация суммы
    try:
        if amount is not None and float(amount) < float(payment.amount or 0):
            return JsonResponse({"error": "Invalid amount"}, status=400)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid amount format"}, status=400)

    payment.status = status
    payment.save(update_fields=["status"])

    if status == "success":
        Enrollment.objects.get_or_create(user=payment.user, course=payment.course)
        payment.course.students.add(payment.user)

    return JsonResponse({"status": "ok"})

# ---------- auth/basic pages ----------

@csrf_protect
def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        
        # django-recaptcha автоматически проверяет капчу в form.is_valid()
        if form.is_valid():
            user = form.save()
            auth_user = authenticate(
                request,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password1"],
            )
            if auth_user is not None:
                login(request, auth_user)
                messages.success(request, "Регистрация прошла успешно! Добро пожаловать!")
                return redirect("home")
            messages.warning(request, "Аккаунт создан, но автологин не сработал. Войдите вручную.")
            return redirect("login")
        else:
            # Если форма невалидна (включая ошибку капчи)
            if 'captcha' in form.errors:
                messages.error(request, "Пожалуйста, пройдите проверку reCAPTCHA.")
            else:
                messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = CustomUserCreationForm()
    
    return render(request, "registration/signup.html", {"form": form})

# ---------- ГЛАВНАЯ СТРАНИЦА (ИСПРАВЛЕННАЯ) ----------

def home(request):
    """Главная страница - ОПТИМИЗИРОВАННАЯ"""
    
    # Ключ кэша только для анонимных пользователей
    language = get_language() or 'ru'
    cache_key = f'home_page_{language}'
    cached_data = cache.get(cache_key)
    
    # Для анонимных пользователей используем кэш
    if cached_data and not request.user.is_authenticated:
        return render(request, "home.html", cached_data)
    
    # Генерируем данные
    try:
        # 1. FEATURED COURSES
        featured_courses_qs = Course.objects.filter(
            is_published=True, 
            is_featured=True
        ).only(
            'id', 'title', 'slug', 'price', 'short_description', 'category_id'
        )[:6]
        
        featured_courses = []
        for course in featured_courses_qs:
            featured_courses.append({
                'id': course.id,
                'title': course.title,
                'slug': course.slug,
                'price': float(course.price or 0),
                'short_description': course.short_description[:100] if course.short_description else '',
                'image_url': f"{settings.STATIC_URL}img/courses/course-placeholder.jpg",
                'url': f"/courses/{course.slug}/",
            })
        
        # Проверяем, является ли students_count полем в БД
        # Если это property, используем аннотацию Count('students')
        if _has_field(Course, 'students_count'):
            # Если это поле в БД
            popular_courses_qs = Course.objects.filter(
                is_published=True
            ).only(
                'id', 'title', 'slug', 'price', 'short_description', 'students_count'
            ).order_by('-students_count', '-created_at')[:6]
        else:
            # Если это property, используем аннотацию
            popular_courses_qs = Course.objects.filter(
                is_published=True
            ).annotate(
                real_students_count=Count('students')
            ).only(
                'id', 'title', 'slug', 'price', 'short_description'
            ).order_by('-real_students_count', '-created_at')[:6]
        
        popular_courses = []
        for course in popular_courses_qs:
            # Получаем students_count в зависимости от типа
            if _has_field(Course, 'students_count'):
                students_count = course.students_count or 0
            else:
                students_count = getattr(course, 'real_students_count', 0) or 0
                
            popular_courses.append({
                'id': course.id,
                'title': course.title,
                'slug': course.slug,
                'price': float(course.price or 0),
                'short_description': course.short_description[:100] if course.short_description else '',
                'students_count': students_count,
                'image_url': f"{settings.STATIC_URL}img/courses/course-placeholder.jpg",
                'url': f"/courses/{course.slug}/",
            })
        
        # 3. CATEGORIES
        categories = list(Category.objects.filter(
            is_active=True
        ).only('id', 'name', 'slug', 'icon')[:8].values('id', 'name', 'slug', 'icon'))
        
        # 4. REVIEWS
        reviews = list(Review.objects.filter(
            is_active=True,
            course__is_published=True
        ).select_related('user', 'course').only(
            'rating', 'comment', 'created_at',
            'user__first_name', 'user__last_name',
            'course__title'
        )[:5].values(
            'rating', 'comment', 'created_at',
            'user__first_name', 'user__last_name',
            'course__title'
        ))
        
        # 5. ARTICLES
        latest_articles_qs = Article.objects.filter(
            is_published=True
        ).only(
            'id', 'title', 'slug', 'excerpt', 'created_at'
        ).order_by('-created_at')[:3]
        
        latest_articles = []
        for article in latest_articles_qs:
            latest_articles.append({
                'id': article.id,
                'title': article.title,
                'slug': article.slug,
                'excerpt': article.excerpt[:150] if article.excerpt else '',
                'image_url': f"{settings.STATIC_URL}img/articles/article-placeholder.jpg",
                'url': f"/articles/{article.slug}/",
            })
            
    except Exception as e:
        # Широкий Exception допустим только на главной,
        # чтобы страница загружалась всегда
        logger.error(f"Ошибка загрузки данных главной: {str(e)}", exc_info=True)
        # Используем пустые данные вместо краха
        featured_courses = []
        popular_courses = []
        categories = []
        reviews = []
        latest_articles = []

    # 6. FAQ (статические)
    faqs = [
        {"question": "Как проходит обучение?", "answer": "Онлайн в личном кабинете: видео, задания и обратная связь."},
        {"question": "Будет ли доступ к материалам после окончания?", "answer": "Да, бессрочный доступ ко всем урокам курса."},
        {"question": "Как оплатить курс?", "answer": "Через Kaspi QR. После оплаты запись активируется автоматически."},
        {"question": "Выдаётся ли сертификат?", "answer": "Да, после завершения всех модулей."},
    ]

    context = {
        "featured_courses": featured_courses,
        "popular_courses": popular_courses,
        "categories": categories,
        "reviews": reviews,
        "latest_articles": latest_articles,
        "latest_materials": [],
        "faqs": faqs,
    }
    
    # Кэшируем только для анонимных пользователей на 3 минуты
    if not request.user.is_authenticated:
        cache.set(cache_key, context, 180)
    
    return render(request, "home.html", context)

@login_required
def toggle_wishlist(request, slug):
    course = get_object_or_404(Course, slug=slug)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, course=course)

    if created:
        message = "Курс добавлен в избранное"
        in_wishlist = True
    else:
        wishlist_item.delete()
        message = "Курс удален из избранного"
        in_wishlist = False

    # AJAX
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "in_wishlist": in_wishlist, "message": message})

    messages.success(request, message)
    return redirect("course_detail", slug=slug)

# ---------- catalog ----------

def catalog(request):
    """Каталог курсов"""
    return redirect('courses_list')

def category_detail(request, slug):
    """Детальная страница категории"""
    try:
        category = Category.objects.get(slug=slug, is_active=True)
        
        courses_qs = Course.objects.filter(
            category=category,
            is_published=True
        ).select_related("category").only(
            'id', 'title', 'slug', 'price', 'short_description',
            'students_count', 'created_at'
        ).order_by('-created_at')
        
        paginator = Paginator(courses_qs, 12)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        
        # Преобразуем в словари
        courses_with_images = []
        for course in page_obj:
            courses_with_images.append({
                'id': course.id,
                'title': course.title,
                'slug': course.slug,
                'price': float(course.price or 0),
                'short_description': course.short_description[:100] if course.short_description else '',
                'students_count': course.students_count or 0,
                'image_url': f"{settings.STATIC_URL}img/courses/course-placeholder.jpg",
                'url': f"/courses/{course.slug}/",
            })
        
        context = {
            "category": category,
            "courses": courses_with_images,
            "is_paginated": page_obj.has_other_pages(),
            "page_obj": page_obj,
        }
        
    except Category.DoesNotExist:
        raise Http404("Категория не найдена")
    except Exception as e:
        logger.error(f"Ошибка загрузки категории {slug}: {str(e)}", exc_info=True)
        raise Http404("Категория не найдена")
    
    return render(request, "categories/detail.html", context)

def courses_list(request):
    """Список курсов - ОПТИМИЗИРОВАННЫЙ"""
    
    search_query = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "newest")
    price_filter = request.GET.get("price")
    category_filter = request.GET.get("category")
    
    # Генерируем ключ кэша
    params = f"{search_query}_{sort_by}_{price_filter}_{category_filter}"
    params_hash = hashlib.md5(params.encode()).hexdigest()[:8]
    cache_key = f'courses_list_{params_hash}'
    
    # Для анонимных - проверяем кэш
    if not request.user.is_authenticated:
        cached_data = cache.get(cache_key)
        if cached_data:
            return render(request, "courses/list.html", cached_data)
    
    # Базовый запрос
    courses_qs = Course.objects.filter(
        is_published=True
    ).select_related("category").only(
        'id', 'title', 'slug', 'price', 'short_description',
        'students_count', 'created_at', 'category_id',
        'category__name', 'category__slug'
    )

    if search_query:
        courses_qs = courses_qs.filter(
            Q(title__icontains=search_query) |
            Q(short_description__icontains=search_query)
        )

    if category_filter:
        courses_qs = courses_qs.filter(category__slug=category_filter)

    if price_filter == "free":
        courses_qs = courses_qs.filter(price=0)
    elif price_filter == "paid":
        courses_qs = courses_qs.filter(price__gt=0)

    # Проверяем тип students_count для сортировки
    if sort_by == "popular":
        if _has_field(Course, 'students_count'):
            courses_qs = courses_qs.order_by("-students_count", "-created_at")
        else:
            courses_qs = courses_qs.annotate(
                real_students_count=Count('students')
            ).order_by("-real_students_count", "-created_at")
    elif sort_by == "rating":
        courses_qs = courses_qs.order_by("-created_at")
    elif sort_by == "price_low":
        courses_qs = courses_qs.order_by("price", "-created_at")
    elif sort_by == "price_high":
        courses_qs = courses_qs.order_by("-price", "-created_at")
    else:
        courses_qs = courses_qs.order_by("-created_at")

    paginator = Paginator(courses_qs, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Преобразуем в словари
    courses_with_images = []
    for course in page_obj:
        # Получаем students_count в зависимости от типа
        if _has_field(Course, 'students_count'):
            students_count = course.students_count or 0
        else:
            students_count = getattr(course, 'real_students_count', 0) or 0
            
        courses_with_images.append({
            'id': course.id,
            'title': course.title,
            'slug': course.slug,
            'price': float(course.price or 0),
            'short_description': course.short_description[:100] if course.short_description else '',
            'category': {
                'name': course.category.name if course.category else '',
                'slug': course.category.slug if course.category else '',
            },
            'students_count': students_count,
            'image_url': f"{settings.STATIC_URL}img/courses/course-placeholder.jpg",
            'url': f"/courses/{course.slug}/",
        })

    # Категории для фильтра
    try:
        categories = list(Category.objects.filter(
            is_active=True
        ).only('id', 'name', 'slug').values('id', 'name', 'slug'))
    except Exception:
        categories = []

    context = {
        "courses": courses_with_images,
        "categories": categories,
        "is_paginated": page_obj.has_other_pages(),
        "page_obj": page_obj,
        "q": search_query,
        "sort_by": sort_by,
    }
    
    # Кэшируем для анонимных на 5 минут
    if not request.user.is_authenticated:
        cache.set(cache_key, context, 300)
    
    return render(request, "courses/list.html", context)

def articles_list(request):
    """Список статей - ОПТИМИЗИРОВАННЫЙ"""
    cache_key = 'articles_list_all'
    
    if not request.user.is_authenticated:
        cached_data = cache.get(cache_key)
        if cached_data:
            return render(request, "articles/list.html", cached_data)
    
    qs = Article.objects.filter(
        is_published=True
    ).only(
        'id', 'title', 'slug', 'excerpt', 'created_at', 'published_at'
    ).order_by('-published_at', '-created_at')
    
    articles = []
    for article in qs:
        articles.append({
            'id': article.id,
            'title': article.title,
            'slug': article.slug,
            'excerpt': article.excerpt[:150] if article.excerpt else '',
            'published_at': article.published_at,
            'created_at': article.created_at,
            'image_url': f"{settings.STATIC_URL}img/articles/article-placeholder.jpg",
            'url': f"/articles/{article.slug}/",
        })
    
    context = {"articles": articles}
    
    # Кэшируем для анонимных на 10 минут
    if not request.user.is_authenticated:
        cache.set(cache_key, context, 600)
    
    return render(request, "articles/list.html", context)

def article_detail(request, slug):
    """Детальная страница статьи - ОПТИМИЗИРОВАННАЯ"""
    cache_key = f'article_detail_{slug}'
    
    if not request.user.is_authenticated:
        cached_data = cache.get(cache_key)
        if cached_data:
            return render(request, "articles/detail.html", cached_data)
    
    try:
        article_obj = Article.objects.filter(
            slug=slug,
            is_published=True
        ).only(
            'id', 'title', 'slug', 'body', 'excerpt', 
            'created_at', 'author_id', 'category_id'
        ).order_by('id').first()
        
        if not article_obj:
            raise Http404("Статья не найдена")
        
        article_data = {
            'id': article_obj.id,
            'title': article_obj.title,
            'slug': article_obj.slug,
            'body': article_obj.body or "",
            'excerpt': article_obj.excerpt or "",
            'created_at': article_obj.created_at,
            'image_url': f"{settings.STATIC_URL}img/articles/article-placeholder.jpg",
        }
        
        # Похожие статьи
        latest_qs = Article.objects.filter(
            is_published=True
        ).exclude(
            pk=article_obj.pk
        ).only(
            'id', 'title', 'slug', 'created_at'
        ).order_by('-created_at')[:4]
        
        latest_articles = []
        for article in latest_qs:
            latest_articles.append({
                'id': article.id,
                'title': article.title,
                'slug': article.slug,
                'image_url': f"{settings.STATIC_URL}img/articles/article-placeholder.jpg",
                'url': f"/articles/{article.slug}/",
            })
        
        context = {
            "article": article_data,
            "latest": latest_articles
        }
        
        # Кэшируем для анонимных на 15 минут
        if not request.user.is_authenticated:
            cache.set(cache_key, context, 900)
        
    except Exception as e:
        logger.error(f"Ошибка загрузки статьи {slug}: {str(e)}", exc_info=True)
        raise Http404("Статья не найдена")
    
    return render(request, "articles/detail.html", context)

def materials_list(request):
    """Список материалов - ОПТИМИЗИРОВАННЫЙ"""
    cache_key = 'materials_list_all'
    
    if not request.user.is_authenticated:
        cached_data = cache.get(cache_key)
        if cached_data:
            return render(request, "materials/list.html", cached_data)
    
    qs = Material.objects.filter(
        is_public=True
    ).only(
        'id', 'title', 'slug', 'description', 'created_at'
    ).order_by('-created_at')[:50]
    
    materials = []
    for material in qs:
        materials.append({
            'id': material.id,
            'title': material.title,
            'slug': material.slug,
            'description': material.description[:150] if material.description else '',
            'image_url': f"{settings.STATIC_URL}img/materials/material-placeholder.jpg",
            'url': f"/materials/{material.slug}/",
        })
    
    context = {"materials": materials}
    
    # Кэшируем для анонимных на 15 минут
    if not request.user.is_authenticated:
        cache.set(cache_key, context, 900)
    
    return render(request, "materials/list.html", context)

# ---------- course detail & lessons ----------

def course_detail(request, slug):
    """Детальная страница курса - ОПТИМИЗИРОВАННАЯ"""
    cache_key = f'course_detail_{slug}'
    
    if not request.user.is_authenticated:
        cached_data = cache.get(cache_key)
        if cached_data:
            # Добавляем персональные данные для авторизованных
            if request.user.is_authenticated:
                cached_data = _enrich_course_data(cached_data, request.user)
            return render(request, "courses/detail.html", cached_data)
    
    try:
        course_obj = Course.objects.filter(
            slug=slug,
            is_published=True
        ).select_related("category", "instructor").only(
            'id', 'title', 'slug', 'price', 'short_description', 'description',
            'category_id', 'category__name', 'category__slug',
            'instructor_id', 'instructor__first_name', 'instructor__last_name',
            'students_count', 'created_at'
        ).order_by('id').first()
        
        if not course_obj:
            raise Http404("Курс не найден")
        
        course_data = {
            'id': course_obj.id,
            'title': course_obj.title,
            'slug': course_obj.slug,
            'price': float(course_obj.price or 0),
            'short_description': course_obj.short_description or "",
            'description': course_obj.description or "",
            'category': {
                'name': course_obj.category.name if course_obj.category else "",
                'slug': course_obj.category.slug if course_obj.category else "",
            },
            'instructor': {
                'name': f"{course_obj.instructor.first_name or ''} {course_obj.instructor.last_name or ''}".strip() if course_obj.instructor else "",
            },
            'students_count': course_obj.students_count or 0,
            'image_url': f"{settings.STATIC_URL}img/courses/course-placeholder.jpg",
        }

        # Доступ
        has_access = False
        is_in_wishlist = False
        if request.user.is_authenticated:
            has_access = Enrollment.objects.filter(
                user=request.user, 
                course=course_obj
            ).exists()
            is_in_wishlist = Wishlist.objects.filter(
                user=request.user, 
                course=course_obj
            ).exists()

        # Модули вместо уроков напрямую
        try:
            modules = list(Module.objects.filter(
                course=course_obj, 
                is_active=True
            ).only(
                'id', 'title', 'order', 'is_active'
            ).order_by("order")[:20])
        except Exception:
            modules = []

        # Похожие курсы
        related_courses_qs = Course.objects.filter(
            category=course_obj.category,
            is_published=True
        ).exclude(id=course_obj.id).only(
            'id', 'title', 'slug', 'price', 'short_description'
        )[:4]
        
        related_courses = []
        for course in related_courses_qs:
            related_courses.append({
                'id': course.id,
                'title': course.title,
                'slug': course.slug,
                'price': float(course.price or 0),
                'short_description': course.short_description[:80] if course.short_description else '',
                'image_url': f"{settings.STATIC_URL}img/courses/course-placeholder.jpg",
                'url': f"/courses/{course.slug}/",
            })

        # Отзывы
        reviews = list(Review.objects.filter(
            course=course_obj, 
            is_active=True
        ).select_related('user').only(
            'rating', 'comment', 'created_at',
            'user__first_name', 'user__last_name'
        )[:10].values(
            'rating', 'comment', 'created_at',
            'user__first_name', 'user__last_name'
        ))

        context = {
            "course": course_data,
            "has_access": has_access,
            "is_in_wishlist": is_in_wishlist,
            "modules": modules,
            "related_courses": related_courses,
            "reviews": reviews,
        }
        
        # Кэшируем для анонимных на 10 минут
        if not request.user.is_authenticated:
            cache.set(cache_key, context, 600)
        
    except Exception as e:
        logger.error(f"Ошибка загрузки курса {slug}: {str(e)}", exc_info=True)
        raise Http404("Курс не найден")
    
    return render(request, "courses/detail.html", context)

def _enrich_course_data(cached_data, user):
    """Добавляет персональные данные к кэшированному курсу"""
    if not user.is_authenticated:
        return cached_data
    
    # Создаём копию сразу, чтобы не мутировать исходный кэш
    result = cached_data.copy()
    
    try:
        course_id = result['course'].get('id')
        if course_id:
            # Проверяем доступ
            has_access = Enrollment.objects.filter(
                user=user, 
                course_id=course_id
            ).exists()
            result['has_access'] = has_access
            
            # Проверяем избранное
            is_in_wishlist = Wishlist.objects.filter(
                user=user, 
                course_id=course_id
            ).exists()
            result['is_in_wishlist'] = is_in_wishlist
            
    except Exception as e:
        logger.error(f"Ошибка обогащения данных курса: {str(e)}", exc_info=True)
    
    return result

def course_learn(request, course_slug):
    """Страница обучения курса"""
    try:
        course_obj = Course.objects.filter(
            slug=course_slug,
            is_published=True
        ).only('id', 'title', 'slug').order_by('id').first()
        
        if not course_obj:
            raise Http404("Курс не найден")
        
        # Проверка доступа
        if not request.user.is_authenticated:
            messages.error(request, "Для доступа к курсу необходимо авторизоваться")
            return redirect('login')
        
        if course_obj.price and float(course_obj.price or 0) > 0:
            has_access = Enrollment.objects.filter(
                user=request.user, 
                course=course_obj
            ).exists()
            if not has_access:
                messages.error(request, "У вас нет доступа к этому курсу")
                return redirect("course_detail", slug=course_slug)
        
        # Получаем первый урок для перенаправления
        first_lesson = Lesson.objects.filter(
            module__course=course_obj,
            is_active=True
        ).order_by("module__order", "order").first()
        
        if first_lesson:
            return redirect("lesson_view", course_slug=course_slug, lesson_slug=first_lesson.slug)
        
        messages.info(request, "В курсе пока нет уроков")
        return redirect("course_detail", slug=course_slug)
        
    except Exception as e:
        logger.error(f"Ошибка загрузки курса для обучения {course_slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке курса")
        return redirect("course_detail", slug=course_slug)

def lesson_view(request, course_slug, lesson_slug):
    """Просмотр урока (альтернативное название для lesson_detail)"""
    return lesson_detail(request, course_slug, lesson_slug)

@login_required
def lesson_detail(request, course_slug, lesson_slug):
    """Детальная страница урока"""
    try:
        course_obj = Course.objects.filter(
            slug=course_slug,
            is_published=True
        ).only('id', 'title', 'slug', 'price').order_by('id').first()
        
        if not course_obj:
            raise Http404("Курс не найден")
        
        # Проверка доступа
        if course_obj.price and float(course_obj.price or 0) > 0:
            has_access = Enrollment.objects.filter(
                user=request.user, 
                course=course_obj
            ).exists()
            if not has_access:
                messages.error(request, "У вас нет доступа к этому уроку")
                return redirect("course_detail", slug=course_slug)
        
        course_data = {
            'id': course_obj.id,
            'title': course_obj.title,
            'slug': course_obj.slug,
            'image_url': f"{settings.STATIC_URL}img/courses/course-placeholder.jpg",
        }

        try:
            lesson = Lesson.objects.filter(
                slug=lesson_slug, 
                module__course=course_obj, 
                is_active=True
            ).select_related("module").only(
                'id', 'title', 'slug', 'content', 'video_url', 'duration',
                'module_id', 'module__title', 'module__order'
            ).order_by('id').first()
            
            if not lesson:
                raise Http404("Урок не найден")
                
        except Exception:
            messages.error(request, "Урок недоступен")
            return redirect("course_detail", slug=course_slug)

        # Соседние уроки
        try:
            lessons_qs = Lesson.objects.filter(
                module__course=course_obj, 
                is_active=True
            ).select_related("module").only(
                'id', 'title', 'slug', 'module__order', 'order'
            ).order_by("module__order", "order")
            
            lessons_list = list(lessons_qs)
            current_index = next((i for i, l in enumerate(lessons_list) if l.id == lesson.id), 0)
            
            previous_lesson = lessons_list[current_index - 1] if current_index > 0 else None
            next_lesson = lessons_list[current_index + 1] if current_index < len(lessons_list) - 1 else None
            
        except Exception:
            previous_lesson = None
            next_lesson = None

        # Обновляем прогресс (BlockProgress вместо LessonProgress)
        try:
            # Для совместимости - создаем BlockProgress, если его нет
            # Но сначала проверяем, есть ли блоки для этого урока
            blocks = LessonBlock.objects.filter(lesson=lesson, is_deleted=False)
            if blocks.exists():
                # Создаем прогресс для первого блока или обновляем существующий
                for block in blocks:
                    BlockProgress.objects.update_or_create(
                        user=request.user,
                        block=block,
                        defaults={
                            "progress_percent": 0,
                            "is_completed": False,
                            "last_accessed": timezone.now(),
                        }
                    )
        except Exception as e:
            logger.error(f"Ошибка создания прогресса для урока {lesson.id}: {str(e)}", exc_info=True)
            pass

        enrollment = Enrollment.objects.filter(
            user=request.user, 
            course=course_obj
        ).first()

        return render(request, "courses/lesson_detail.html", {
            "course": course_data,
            "lesson": lesson,
            "prev_lesson": previous_lesson,
            "next_lesson": next_lesson,
            "enrollment": enrollment,
        })
        
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Ошибка загрузки урока {course_slug}/{lesson_slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке урока")
        return redirect("courses_list")

@login_required
def update_progress(request):
    """Обновление прогресса урока"""
    if request.method == "POST":
        try:
            lesson_id = request.POST.get("lesson_id")
            progress = request.POST.get("progress", 0)
            
            if not lesson_id:
                return JsonResponse({"error": "lesson_id required"}, status=400)
            
            try:
                progress = int(progress)
                progress = max(0, min(100, progress))
            except ValueError:
                return JsonResponse({"error": "Invalid progress value"}, status=400)
            
            # Ищем урок
            lesson = Lesson.objects.get(id=lesson_id)
            
            # Обновляем прогресс первого блока урока
            block = LessonBlock.objects.filter(lesson=lesson, is_deleted=False).first()
            if block:
                block_progress, created = BlockProgress.objects.update_or_create(
                    user=request.user,
                    block=block,
                    defaults={
                        "progress_percent": progress,
                        "is_completed": progress >= 100,
                        "last_accessed": timezone.now(),
                    }
                )
                
                # Если урок завершен (100%), проверяем завершение курса
                if progress >= 100:
                    _check_course_completion(request.user, lesson.module.course)
                
                return JsonResponse({
                    "success": True,
                    "progress": progress,
                    "is_completed": progress >= 100,
                })
            else:
                return JsonResponse({"error": "No blocks found for this lesson"}, status=404)
                
        except Lesson.DoesNotExist:
            return JsonResponse({"error": "Lesson not found"}, status=404)
        except Exception as e:
            logger.error(f"Ошибка обновления прогресса: {str(e)}", exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

def _check_course_completion(user, course):
    """Проверка завершения курса"""
    try:
        # Получаем все обязательные блоки курса
        required_blocks = LessonBlock.objects.filter(
            lesson__module__course=course,
            is_required=True,
            is_deleted=False
        ).count()
        
        if required_blocks == 0:
            return
        
        # Получаем завершенные блоки пользователя
        completed_blocks = BlockProgress.objects.filter(
            user=user,
            block__lesson__module__course=course,
            is_completed=True
        ).count()
        
        # Если все обязательные блоки завершены, отмечаем курс как завершенный
        if completed_blocks >= required_blocks:
            enrollment = Enrollment.objects.get(user=user, course=course)
            if not enrollment.completed:
                enrollment.completed = True
                enrollment.completed_at = timezone.now()
                enrollment.save()
                
    except Exception as e:
        logger.error(f"Ошибка проверки завершения курса: {str(e)}", exc_info=True)

# ---------- enrollment & payments ----------

@login_required
def enroll_course(request, slug):
    """Запись на курс"""
    try:
        course = Course.objects.filter(
            slug=slug,
            is_published=True
        ).only('id', 'slug').order_by('id').first()
        
        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")
        
        Enrollment.objects.get_or_create(user=request.user, course=course)
        
        # Получаем первый доступный урок
        first_lesson = Lesson.objects.filter(
            module__course=course,
            is_active=True
        ).order_by("module__order", "order").first()
        
        if first_lesson:
            return redirect("lesson_view", course_slug=course.slug, lesson_slug=first_lesson.slug)
        else:
            messages.success(request, "Вы успешно записались на курс!")
            return redirect("course_detail", slug=slug)
            
    except Exception as e:
        logger.error(f"Ошибка записи на курс {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при записи на курс")
        return redirect("course_detail", slug=slug)

def checkout(request, slug):
    """Страница оформления заказа"""
    return create_payment(request, slug)

@login_required
def create_payment(request, slug):
    """Создание платежа"""
    try:
        course = Course.objects.filter(
            slug=slug,
            is_published=True
        ).only('id', 'title', 'slug', 'price').order_by('id').first()
        
        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")
        
        amount = course.discount_price or course.price or 0
        payment = Payment.objects.create(
            user=request.user,
            course=course,
            amount=amount,
            status="pending",
            kaspi_invoice_id=f"QR{int(timezone.now().timestamp())}",
        )
        
        return render(request, "payments/payment_page.html", {
            "course": {
                'title': course.title,
                'slug': course.slug,
            },
            "amount": amount,
            "kaspi_url": getattr(settings, "KASPI_PAYMENT_URL", ""),
            "payment": payment,
        })
        
    except Exception as e:
        logger.error(f"Ошибка создания платежа {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при создании платежа")
        return redirect("course_detail", slug=slug)

def checkout_confirm(request, slug):
    """Подтверждение оформления заказа"""
    return payment_claim(request, slug)

@login_required
def payment_claim(request, slug):
    """Подтверждение платежа"""
    try:
        course = Course.objects.filter(slug=slug).only('id', 'title', 'slug').order_by('id').first()
        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")

        payment = Payment.objects.filter(
            user=request.user, 
            course=course
        ).order_by("-id").first()
        
        if not payment:
            messages.error(request, "Платеж не найден")
            return redirect("course_detail", slug=slug)

        if request.method == "POST" and request.FILES.get("receipt"):
            if hasattr(payment, "receipt"):
                payment.receipt = request.FILES["receipt"]
                payment.save(update_fields=["receipt"])
                messages.success(request, "Чек успешно загружен, ожидайте подтверждения")
                return redirect("payment_thanks", slug=slug)
            messages.error(request, "В модели Payment не предусмотрено поле для чека")

        return render(request, "payments/payment_claim.html", {
            "course": {
                'title': course.title,
                'slug': course.slug,
            },
            "payment": payment,
        })
        
    except Exception as e:
        logger.error(f"Ошибка подтверждения платежа {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка")
        return redirect("course_detail", slug=slug)

def payment_webhook(request):
    """Webhook для платежей"""
    return kaspi_webhook(request)

@login_required
def payment_thanks(request, slug):
    """Страница благодарности за платеж"""
    try:
        course = Course.objects.filter(slug=slug).only('id', 'title', 'slug').order_by('id').first()
        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")
            
        return render(request, "payments/payment_thanks.html", {
            "course": {
                'title': course.title,
                'slug': course.slug,
            },
        })
        
    except Exception as e:
        logger.error(f"Ошибка страницы благодарности {slug}: {str(e)}", exc_info=True)
        return redirect("courses_list")

# ---------- user area ----------

@login_required
def my_courses(request):
    """Мои курсы"""
    try:
        enrollments = Enrollment.objects.filter(
            user=request.user
        ).select_related("course").only(
            'id', 'completed', 'progress', 'created_at',
            'course_id', 'course__title', 'course__slug', 'course__short_description'
        ).order_by('-created_at')
        
        courses_with_images = []
        for enrollment in enrollments:
            courses_with_images.append({
                'id': enrollment.course.id,
                'title': enrollment.course.title,
                'slug': enrollment.course.slug,
                'short_description': enrollment.course.short_description[:100] if enrollment.course.short_description else '',
                'image_url': f"{settings.STATIC_URL}img/courses/course-placeholder.jpg",
                'url': f"/courses/{enrollment.course.slug}/",
                'enrollment': {
                    'completed': enrollment.completed,
                    'progress': enrollment.progress,
                    'created_at': enrollment.created_at,
                },
            })
        
        in_progress = [c for c in courses_with_images if not c["enrollment"]['completed']]
        completed = [c for c in courses_with_images if c["enrollment"]['completed']]
        
        return render(request, "courses/my_courses.html", {
            "in_progress": in_progress,
            "completed": completed,
        })
        
    except Exception as e:
        logger.error(f"Ошибка загрузки моих курсов: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке курсов")
        return render(request, "courses/my_courses.html", {
            "in_progress": [],
            "completed": [],
        })

@login_required
def dashboard(request):
    """Дашборд пользователя"""
    try:
        user = request.user
        
        # Мои курсы
        my_courses_qs = Course.objects.filter(
            students__id=user.id
        ).only('id', 'title', 'slug', 'created_at')[:10]
        
        my_courses = []
        for course in my_courses_qs:
            my_courses.append({
                'id': course.id,
                'title': course.title,
                'slug': course.slug,
                'image_url': f"{settings.STATIC_URL}img/courses/course-placeholder.jpg",
                'url': f"/courses/{course.slug}/",
                'created_at': course.created_at,
            })
        
        total_courses = len(my_courses)
        recent_courses = sorted(my_courses, key=lambda x: x['created_at'], reverse=True)[:5]

        # Завершенные курсы
        completed_courses = Enrollment.objects.filter(
            user_id=user.id, 
            completed=True
        ).count()

        # Прогресс блоков вместо уроков
        try:
            progress_qs = BlockProgress.objects.filter(user=user)
            total_blocks = progress_qs.count()
            completed_blocks = progress_qs.filter(is_completed=True).count()
        except Exception:
            total_blocks = 0
            completed_blocks = 0

        context = {
            "total_courses": total_courses,
            "completed_courses": completed_courses,
            "total_blocks": total_blocks,
            "completed_blocks": completed_blocks,
            "recent_courses": recent_courses,
        }
        
    except Exception as e:
        logger.error(f"Ошибка дашборда: {str(e)}", exc_info=True)
        context = {
            "total_courses": 0,
            "completed_courses": 0,
            "total_blocks": 0,
            "completed_blocks": 0,
            "recent_courses": [],
        }
    
    return render(request, "users/dashboard.html", context)

def learning_dashboard(request):
    """Дашборд обучения (алиас для dashboard)"""
    return dashboard(request)

@login_required
def profile_settings(request):
    """Настройки профиля - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    # Гарантируем создание профиля
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'phone': '',
            'city': '',
            'balance': 0,
            'role': 'student',
            'bio': '',
            'company': '',
            'position': '',
            'website': '',
            'country': '',
            'email_notifications': True,
            'course_updates': True,
            'newsletter': False,
            'push_reminders': True,
        }
    )
    
    user = request.user
    
    if request.method == 'POST':
        # Устанавливаем активную вкладку по умолчанию
        active_tab = 'profile'
        
        try:
            if 'update_profile' in request.POST:
                # Обновление профиля
                try:
                    first_name = request.POST.get('first_name', '').strip()
                    last_name = request.POST.get('last_name', '').strip()
                    
                    if first_name:
                        user.first_name = first_name
                    if last_name:
                        user.last_name = last_name
                    
                    # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Аватар сохраняем в profile, а не в user
                    if 'avatar' in request.FILES:
                        profile.avatar = request.FILES['avatar']
                    
                    # Дополнительные поля профиля
                    profile.phone = request.POST.get('phone', '').strip()
                    profile.bio = request.POST.get('bio', '').strip()
                    profile.company = request.POST.get('company', '').strip()
                    profile.position = request.POST.get('position', '').strip()
                    profile.website = request.POST.get('website', '').strip()
                    profile.country = request.POST.get('country', '').strip()
                    profile.city = request.POST.get('city', '').strip()
                    profile.save()
                    
                    user.save()
                    messages.success(request, 'Настройки профиля успешно обновлены!')
                except Exception as e:
                    logger.error(f"Ошибка обновления профиля: {str(e)}", exc_info=True)
                    messages.error(request, 'Произошла ошибка при обновлении профиля')
                
                active_tab = 'profile'
            
            elif 'change_password' in request.POST:
                # Смена пароля
                try:
                    current_password = request.POST.get('current_password', '')
                    new_password1 = request.POST.get('new_password1', '')
                    new_password2 = request.POST.get('new_password2', '')
                    
                    if user.check_password(current_password):
                        if new_password1 == new_password2:
                            if len(new_password1) >= 8:
                                user.set_password(new_password1)
                                user.save()
                                update_session_auth_hash(request, user)
                                messages.success(request, 'Пароль успешно изменен!')
                            else:
                                messages.error(request, 'Пароль должен содержать минимум 8 символов')
                        else:
                            messages.error(request, 'Новые пароли не совпадают')
                    else:
                        messages.error(request, 'Текущий пароль неверен')
                except Exception as e:
                    logger.error(f"Ошибка смены пароля: {str(e)}", exc_info=True)
                    messages.error(request, 'Произошла ошибка при смене пароля')
                
                active_tab = 'security'
                
            elif 'update_notifications' in request.POST:
                # Обновление настроек уведомлений
                try:
                    profile.email_notifications = 'email_notifications' in request.POST
                    profile.course_updates = 'course_updates' in request.POST
                    profile.newsletter = 'newsletter' in request.POST
                    profile.push_reminders = 'push_reminders' in request.POST
                    profile.save()
                    messages.success(request, 'Настройки уведомлений сохранены!')
                except Exception as e:
                    logger.error(f"Ошибка обновления настроек уведомлений: {str(e)}", exc_info=True)
                    messages.error(request, 'Произошла ошибка при сохранении настроек уведомлений')
                
                active_tab = 'notifications'
            
            # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Всегда возвращаем активную вкладку
            return redirect(f'{request.path}?tab={active_tab}')
            
        except Exception as e:
            logger.error(f"Общая ошибка обработки формы профиля: {str(e)}", exc_info=True)
            messages.error(request, 'Произошла ошибка при сохранении настроек')
    
    # GET запрос
    active_tab = request.GET.get('tab', 'profile')
    
    context = {
        'user': user,
        'profile': profile,
        'active_tab': active_tab,
    }
    
    return render(request, "users/profile_settings.html", context)

def account_settings(request):
    """Настройки аккаунта (алиас для profile_settings)"""
    return profile_settings(request)

@login_required
def add_review(request, slug):
    """Добавление отзыва"""
    try:
        course = Course.objects.filter(
            slug=slug,
            is_published=True
        ).only('id', 'title', 'slug').order_by('id').first()
        
        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")

        # Проверка доступа
        has_access = Enrollment.objects.filter(
            user=request.user, 
            course=course
        ).exists()
        
        if not has_access:
            messages.error(request, "Только студенты курса могут оставлять отзывы")
            return redirect("course_detail", slug=slug)

        # Проверка существующего отзыва
        if Review.objects.filter(course=course, user=request.user).exists():
            messages.error(request, "Вы уже оставили отзыв на этот курс")
            return redirect("course_detail", slug=slug)

        if request.method == "POST":
            form = ReviewForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.course = course
                review.user = request.user
                review.save()
                messages.success(request, "Ваш отзыв успешно добавлен")
                return redirect("course_detail", slug=slug)
        else:
            form = ReviewForm()

        return render(request, "courses/add_review.html", {
            "course": {
                'title': course.title,
                'slug': course.slug,
            },
            "form": form,
        })
        
    except Exception as e:
        logger.error(f"Ошибка добавления отзыва {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка")
        return redirect("course_detail", slug=slug)

# ---------- instructor area ----------

@login_required
def instructor_dashboard(request):
    """Дашборд инструктора"""
    if not request.user.is_staff and not request.user.is_superuser:
        # Проверяем, является ли пользователь инструктором
        is_instructor = Course.objects.filter(instructor=request.user).exists() or \
                       CourseStaff.objects.filter(user=request.user, role__in=['owner', 'instructor']).exists()
        if not is_instructor:
            messages.error(request, "У вас нет прав доступа к панели инструктора")
            return redirect('learning_dashboard')
    
    try:
        user = request.user
        
        # Курсы инструктора
        instructor_courses = Course.objects.filter(
            Q(instructor=user) | 
            Q(staff__user=user, staff__role__in=['owner', 'instructor'])
        ).distinct().only('id', 'title', 'slug', 'status', 'created_at')[:10]
        
        courses_data = []
        for course in instructor_courses:
            students_count = Enrollment.objects.filter(course=course).count()
            total_revenue = Payment.objects.filter(course=course, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
            
            courses_data.append({
                'id': course.id,
                'title': course.title,
                'slug': course.slug,
                'status': course.status,
                'students_count': students_count,
                'revenue': total_revenue,
                'url': f"/courses/{course.slug}/",
            })
        
        # Общая статистика
        total_courses = len(courses_data)
        total_students = Enrollment.objects.filter(
            course__in=[c['id'] for c in courses_data]
        ).values('user').distinct().count()
        total_revenue = sum(c['revenue'] for c in courses_data)
        
        context = {
            'courses': courses_data,
            'total_courses': total_courses,
            'total_students': total_students,
            'total_revenue': total_revenue,
        }
        
    except Exception as e:
        logger.error(f"Ошибка загрузки дашборда инструктора: {str(e)}", exc_info=True)
        context = {
            'courses': [],
            'total_courses': 0,
            'total_students': 0,
            'total_revenue': 0,
        }
    
    return render(request, "instructor/dashboard.html", context)

@login_required
def instructor_courses(request):
    """Курсы инструктора"""
    if not request.user.is_staff and not request.user.is_superuser:
        is_instructor = Course.objects.filter(instructor=request.user).exists() or \
                       CourseStaff.objects.filter(user=request.user, role__in=['owner', 'instructor']).exists()
        if not is_instructor:
            messages.error(request, "У вас нет прав доступа")
            return redirect('learning_dashboard')
    
    try:
        courses = Course.objects.filter(
            Q(instructor=request.user) | 
            Q(staff__user=request.user, staff__role__in=['owner', 'instructor'])
        ).distinct().select_related('category').only(
            'id', 'title', 'slug', 'status', 'category__name',
            'created_at', 'students_count'
        ).order_by('-created_at')
        
        # Добавляем статистику
        courses_with_stats = []
        for course in courses:
            students = Enrollment.objects.filter(course=course).count()
            revenue = Payment.objects.filter(course=course, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
            reviews = Review.objects.filter(course=course, is_active=True).count()
            
            courses_with_stats.append({
                'course': course,
                'students': students,
                'revenue': revenue,
                'reviews': reviews,
            })
        
        context = {
            'courses': courses_with_stats,
        }
        
    except Exception as e:
        logger.error(f"Ошибка загрузки курсов инструктора: {str(e)}", exc_info=True)
        context = {
            'courses': [],
        }
    
    return render(request, "instructor/courses.html", context)

@login_required
def instructor_course_detail(request, slug):
    """Детальная страница курса инструктора"""
    try:
        course = Course.objects.get(slug=slug)
        
        # Проверка прав
        has_access = (
            request.user.is_staff or 
            request.user.is_superuser or
            course.instructor == request.user or
            CourseStaff.objects.filter(course=course, user=request.user, role__in=['owner', 'instructor']).exists()
        )
        
        if not has_access:
            messages.error(request, "У вас нет прав доступа к этому курсу")
            return redirect('instructor_courses')
        
        # Статистика
        enrollments = Enrollment.objects.filter(course=course)
        payments = Payment.objects.filter(course=course, status='success')
        reviews = Review.objects.filter(course=course, is_active=True)
        
        # Прогресс студентов
        students_progress = []
        for enrollment in enrollments.select_related('user')[:20]:
            completed_blocks = BlockProgress.objects.filter(
                user=enrollment.user,
                block__lesson__module__course=course,
                is_completed=True
            ).count()
            
            total_blocks = LessonBlock.objects.filter(
                lesson__module__course=course,
                is_required=True,
                is_deleted=False
            ).count()
            
            progress = round((completed_blocks / total_blocks * 100), 1) if total_blocks > 0 else 0
            
            students_progress.append({
                'user': enrollment.user,
                'enrolled_at': enrollment.enrolled_at,
                'progress': progress,
                'completed': enrollment.completed,
            })
        
        context = {
            'course': course,
            'total_students': enrollments.count(),
            'total_revenue': payments.aggregate(Sum('amount'))['amount__sum'] or 0,
            'average_rating': reviews.aggregate(Avg('rating'))['rating__avg'] or 0,
            'students_progress': students_progress,
        }
        
    except Course.DoesNotExist:
        raise Http404("Курс не найден")
    except Exception as e:
        logger.error(f"Ошибка загрузки деталей курса инструктора {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке данных курса")
        return redirect('instructor_courses')
    
    return render(request, "instructor/course_detail.html", context)

@login_required
def instructor_analytics(request):
    """Аналитика инструктора"""
    if not request.user.is_staff and not request.user.is_superuser:
        is_instructor = Course.objects.filter(instructor=request.user).exists() or \
                       CourseStaff.objects.filter(user=request.user, role__in=['owner', 'instructor']).exists()
        if not is_instructor:
            messages.error(request, "У вас нет прав доступа")
            return redirect('learning_dashboard')
    
    try:
        # Получаем курсы инструктора
        courses = Course.objects.filter(
            Q(instructor=request.user) | 
            Q(staff__user=request.user, staff__role__in=['owner', 'instructor'])
        ).distinct()
        
        # Общая статистика
        total_courses = courses.count()
        total_enrollments = Enrollment.objects.filter(course__in=courses).count()
        total_revenue = Payment.objects.filter(course__in=courses, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        total_reviews = Review.objects.filter(course__in=courses, is_active=True).count()
        
        # Статистика по месяцам
        months_data = []
        for i in range(5, -1, -1):
            month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30*i)
            month_end = month_start + timedelta(days=30)
            
            month_enrollments = Enrollment.objects.filter(
                course__in=courses,
                enrolled_at__gte=month_start,
                enrolled_at__lt=month_end
            ).count()
            
            month_revenue = Payment.objects.filter(
                course__in=courses,
                status='success',
                paid_at__gte=month_start,
                paid_at__lt=month_end
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            months_data.append({
                'month': month_start.strftime('%b %Y'),
                'enrollments': month_enrollments,
                'revenue': month_revenue,
            })
        
        context = {
            'total_courses': total_courses,
            'total_enrollments': total_enrollments,
            'total_revenue': total_revenue,
            'total_reviews': total_reviews,
            'months_data': months_data,
        }
        
    except Exception as e:
        logger.error(f"Ошибка загрузки аналитики инструктора: {str(e)}", exc_info=True)
        context = {
            'total_courses': 0,
            'total_enrollments': 0,
            'total_revenue': 0,
            'total_reviews': 0,
            'months_data': [],
        }
    
    return render(request, "instructor/analytics.html", context)

@login_required
def instructor_students(request):
    """Студенты инструктора"""
    if not request.user.is_staff and not request.user.is_superuser:
        is_instructor = Course.objects.filter(instructor=request.user).exists() or \
                       CourseStaff.objects.filter(user=request.user, role__in=['owner', 'instructor']).exists()
        if not is_instructor:
            messages.error(request, "У вас нет прав доступа")
            return redirect('learning_dashboard')
    
    try:
        # Получаем курсы инструктора
        courses = Course.objects.filter(
            Q(instructor=request.user) | 
            Q(staff__user=request.user, staff__role__in=['owner', 'instructor'])
        ).distinct()
        
        # Получаем студентов
        students = User.objects.filter(
            enrollments__course__in=courses
        ).distinct().select_related('profile').prefetch_related(
            'enrollments', 'enrollments__course'
        )[:50]  # Ограничиваем для производительности
        
        students_data = []
        for student in students:
            # Курсы студента
            student_courses = Enrollment.objects.filter(
                user=student,
                course__in=courses
            ).select_related('course')[:5]
            
            courses_list = []
            for enrollment in student_courses:
                # Прогресс по курсу
                completed_blocks = BlockProgress.objects.filter(
                    user=student,
                    block__lesson__module__course=enrollment.course,
                    is_completed=True
                ).count()
                
                total_blocks = LessonBlock.objects.filter(
                    lesson__module__course=enrollment.course,
                    is_required=True,
                    is_deleted=False
                ).count()
                
                progress = round((completed_blocks / total_blocks * 100), 1) if total_blocks > 0 else 0
                
                courses_list.append({
                    'course': enrollment.course,
                    'enrolled_at': enrollment.enrolled_at,
                    'completed': enrollment.completed,
                    'progress': progress,
                })
            
            students_data.append({
                'student': student,
                'courses': courses_list,
                'total_courses': student_courses.count(),
            })
        
        context = {
            'students': students_data,
        }
        
    except Exception as e:
        logger.error(f"Ошибка загрузки студентов инструктора: {str(e)}", exc_info=True)
        context = {
            'students': [],
        }
    
    return render(request, "instructor/students.html", context)

# ---------- API endpoints ----------

def api_courses(request):
    """API для получения списка курсов"""
    try:
        courses = Course.objects.filter(
            is_published=True
        ).only('id', 'title', 'slug', 'price', 'short_description')[:50]
        
        courses_list = []
        for course in courses:
            courses_list.append({
                'id': course.id,
                'title': course.title,
                'slug': course.slug,
                'price': float(course.price or 0),
                'short_description': course.short_description[:200] if course.short_description else '',
                'url': f"{request.scheme}://{request.get_host()}/courses/{course.slug}/",
            })
        
        return JsonResponse({
            'status': 'success',
            'count': len(courses_list),
            'courses': courses_list,
        })
        
    except Exception as e:
        logger.error(f"Ошибка API курсов: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error',
        }, status=500)

@login_required
def api_enroll(request):
    """API для записи на курс"""
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Method not allowed',
        }, status=405)
    
    try:
        course_slug = request.POST.get('course_slug')
        if not course_slug:
            return JsonResponse({
                'status': 'error',
                'message': 'course_slug is required',
            }, status=400)
        
        course = Course.objects.filter(
            slug=course_slug,
            is_published=True
        ).first()
        
        if not course:
            return JsonResponse({
                'status': 'error',
                'message': 'Course not found',
            }, status=404)
        
        # Проверяем, не записан ли уже
        if Enrollment.objects.filter(user=request.user, course=course).exists():
            return JsonResponse({
                'status': 'success',
                'message': 'Already enrolled',
                'enrolled': True,
            })
        
        # Записываем
        Enrollment.objects.create(user=request.user, course=course)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Successfully enrolled',
            'enrolled': True,
        })
        
    except Exception as e:
        logger.error(f"Ошибка API записи: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error',
        }, status=500)

def api_reviews(request):
    """API для получения отзывов"""
    try:
        course_slug = request.GET.get('course_slug')
        
        if course_slug:
            reviews_qs = Review.objects.filter(
                course__slug=course_slug,
                is_active=True
            ).select_related('user', 'course')[:20]
        else:
            reviews_qs = Review.objects.filter(
                is_active=True
            ).select_related('user', 'course')[:20]
        
        reviews_list = []
        for review in reviews_qs:
            reviews_list.append({
                'id': review.id,
                'rating': review.rating,
                'comment': review.comment,
                'created_at': review.created_at.isoformat(),
                'user': {
                    'username': review.user.username,
                    'name': f"{review.user.first_name or ''} {review.user.last_name or ''}".strip(),
                },
                'course': {
                    'title': review.course.title,
                    'slug': review.course.slug,
                } if review.course else None,
            })
        
        return JsonResponse({
            'status': 'success',
            'count': len(reviews_list),
            'reviews': reviews_list,
        })
        
    except Exception as e:
        logger.error(f"Ошибка API отзывов: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error',
        }, status=500)

# ---------- CRM area ----------

@login_required
def crm_dashboard(request):
    """CRM дашборд (только для staff)"""
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "У вас нет прав доступа к CRM")
        return redirect('learning_dashboard')
    
    try:
        # Статистика
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Новые лиды за период
        new_leads_today = Lead.objects.filter(created_at__date=today).count()
        new_leads_week = Lead.objects.filter(created_at__gte=week_ago).count()
        new_leads_month = Lead.objects.filter(created_at__gte=month_ago).count()
        
        # Конвертированные лиды
        converted_leads_today = Lead.objects.filter(converted=True, converted_at__date=today).count()
        converted_leads_week = Lead.objects.filter(converted=True, converted_at__gte=week_ago).count()
        converted_leads_month = Lead.objects.filter(converted=True, converted_at__gte=month_ago).count()
        
        # Платежи
        payments_today = Payment.objects.filter(created_at__date=today, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        payments_week = Payment.objects.filter(created_at__gte=week_ago, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        payments_month = Payment.objects.filter(created_at__gte=month_ago, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Конверсия
        conversion_rate_today = round((converted_leads_today / new_leads_today * 100), 1) if new_leads_today > 0 else 0
        conversion_rate_week = round((converted_leads_week / new_leads_week * 100), 1) if new_leads_week > 0 else 0
        conversion_rate_month = round((converted_leads_month / new_leads_month * 100), 1) if new_leads_month > 0 else 0
        
        context = {
            'new_leads_today': new_leads_today,
            'new_leads_week': new_leads_week,
            'new_leads_month': new_leads_month,
            'converted_leads_today': converted_leads_today,
            'converted_leads_week': converted_leads_week,
            'converted_leads_month': converted_leads_month,
            'payments_today': payments_today,
            'payments_week': payments_week,
            'payments_month': payments_month,
            'conversion_rate_today': conversion_rate_today,
            'conversion_rate_week': conversion_rate_week,
            'conversion_rate_month': conversion_rate_month,
        }
        
    except Exception as e:
        logger.error(f"Ошибка загрузки CRM дашборда: {str(e)}", exc_info=True)
        context = {
            'new_leads_today': 0,
            'new_leads_week': 0,
            'new_leads_month': 0,
            'converted_leads_today': 0,
            'converted_leads_week': 0,
            'converted_leads_month': 0,
            'payments_today': 0,
            'payments_week': 0,
            'payments_month': 0,
            'conversion_rate_today': 0,
            'conversion_rate_week': 0,
            'conversion_rate_month': 0,
        }
    
    return render(request, "crm/dashboard.html", context)

@login_required
def crm_leads(request):
    """Управление лидами (только для staff)"""
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "У вас нет прав доступа к CRM")
        return redirect('learning_dashboard')
    
    try:
        leads = Lead.objects.all().select_related('assigned_to').order_by('-created_at')
        
        # Фильтрация
        status_filter = request.GET.get('status')
        if status_filter:
            leads = leads.filter(status=status_filter)
        
        # Поиск
        search_query = request.GET.get('q')
        if search_query:
            leads = leads.filter(
                Q(email__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(phone__icontains=search_query)
            )
        
        # Пагинация
        paginator = Paginator(leads, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'leads': page_obj,
            'status_filter': status_filter,
            'search_query': search_query or '',
        }
        
    except Exception as e:
        logger.error(f"Ошибка загрузки лидов CRM: {str(e)}", exc_info=True)
        context = {
            'leads': [],
            'status_filter': '',
            'search_query': '',
        }
    
    return render(request, "crm/leads.html", context)

@login_required
def crm_payments(request):
    """Управление платежами (только для staff)"""
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "У вас нет прав доступа к CRM")
        return redirect('learning_dashboard')
    
    try:
        payments = Payment.objects.all().select_related('user', 'course').order_by('-created_at')
        
        # Фильтрация
        status_filter = request.GET.get('status')
        if status_filter:
            payments = payments.filter(status=status_filter)
        
        # Поиск
        search_query = request.GET.get('q')
        if search_query:
            payments = payments.filter(
                Q(user__username__icontains=search_query) |
                Q(user__email__icontains=search_query) |
                Q(course__title__icontains=search_query) |
                Q(payment_id__icontains=search_query)
            )
        
        # Пагинация
        paginator = Paginator(payments, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Статистика
        total_revenue = Payment.objects.filter(status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        pending_payments = Payment.objects.filter(status='pending').count()
        failed_payments = Payment.objects.filter(status='failed').count()
        
        context = {
            'payments': page_obj,
            'status_filter': status_filter,
            'search_query': search_query or '',
            'total_revenue': total_revenue,
            'pending_payments': pending_payments,
            'failed_payments': failed_payments,
        }
        
    except Exception as e:
        logger.error(f"Ошибка загрузки платежей CRM: {str(e)}", exc_info=True)
        context = {
            'payments': [],
            'status_filter': '',
            'search_query': '',
            'total_revenue': 0,
            'pending_payments': 0,
            'failed_payments': 0,
        }
    
    return render(request, "crm/payments.html", context)

# ---------- static pages ----------

def about(request):
    """О нас"""
    cache_key = 'about_page_data'
    
    cached_data = cache.get(cache_key)
    if cached_data:
        return render(request, "about.html", cached_data)
    
    try:
        instructors = list(InstructorProfile.objects.filter(
            is_approved=True
        ).select_related('user').only(
            'id', 'bio', 'title', 'company',
            'user__first_name', 'user__last_name'
        )[:10].values(
            'id', 'bio', 'title', 'company',
            'user__first_name', 'user__last_name'
        ))
        
        total_instructors = len(instructors)
        
        stats = {
            "total_courses": Course.objects.filter(is_published=True).count(),
            "total_students": Enrollment.objects.values('user').distinct().count(),
            "total_instructors": total_instructors,
        }
        
    except Exception as e:
        logger.error(f"Ошибка загрузки страницы 'О нас': {str(e)}", exc_info=True)
        instructors = []
        stats = {"total_courses": 0, "total_students": 0, "total_instructors": 0}

    context = {
        "instructors": instructors,
        "stats": stats,
    }
    
    # Кэшируем на 30 минут
    cache.set(cache_key, context, 1800)
    
    return render(request, "about.html", context)

def contact(request):
    """Контакты"""
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Ваше сообщение успешно отправлено!")
            except Exception as e:
                logger.error(f"Ошибка сохранения контакта: {str(e)}", exc_info=True)
                messages.error(request, "Произошла ошибка при отправке сообщения")
            return redirect("contact")
    else:
        form = ContactForm()
    
    return render(request, "contact.html", {"form": form})

def design_wireframe(request):
    """Дизайн-макет"""
    cache_key = 'design_wireframe_data'
    
    cached_data = cache.get(cache_key)
    if cached_data:
        return render(request, "design_wireframe.html", cached_data)
    
    features = [
        {"title": "Практика", "description": "Проекты в портфолио"},
        {"title": "Наставник", "description": "Обратная связь"},
        {"title": "Гибкий формат", "description": "Онлайн и записи"},
        {"title": "Комьюнити", "description": "Чаты и ревью"},
        {"title": "Карьерный трек", "description": "Помощь с резюме"},
        {"title": "Сертификат", "description": "После защиты"},
    ]
    
    context = {"features": features}
    
    # Кэшируем на 1 час
    cache.set(cache_key, context, 3600)
    
    return render(request, "design_wireframe.html", context)

# ---------- service pages ----------

def health_check(request):
    """Проверка здоровья приложения"""
    try:
        # Проверяем подключение к базе данных
        Course.objects.count()
        
        # Проверяем кэш
        cache.set('health_check', 'ok', 1)
        if cache.get('health_check') != 'ok':
            raise Exception("Cache not working")
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'database': 'ok',
            'cache': 'ok',
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'error': str(e),
        }, status=500)

def sitemap(request):
    """Генерация sitemap.xml"""
    try:
        # Базовые URL
        urls = [
            {'loc': reverse('home'), 'priority': '1.0'},
            {'loc': reverse('about'), 'priority': '0.8'},
            {'loc': reverse('contact'), 'priority': '0.8'},
            {'loc': reverse('courses_list'), 'priority': '0.9'},
            {'loc': reverse('articles_list'), 'priority': '0.7'},
            {'loc': reverse('materials_list'), 'priority': '0.7'},
        ]
        
        # Курсы
        courses = Course.objects.filter(is_published=True).only('slug', 'updated_at')[:1000]
        for course in courses:
            urls.append({
                'loc': reverse('course_detail', args=[course.slug]),
                'lastmod': course.updated_at.strftime('%Y-%m-%d'),
                'priority': '0.8',
            })
        
        # Статьи
        articles = Article.objects.filter(is_published=True).only('slug', 'updated_at')[:1000]
        for article in articles:
            urls.append({
                'loc': reverse('article_detail', args=[article.slug]),
                'lastmod': article.updated_at.strftime('%Y-%m-%d'),
                'priority': '0.6',
            })
        
        # Категории
        categories = Category.objects.filter(is_active=True).only('slug', 'updated_at')[:100]
        for category in categories:
            urls.append({
                'loc': reverse('category_detail', args=[category.slug]),
                'lastmod': category.updated_at.strftime('%Y-%m-%d'),
                'priority': '0.5',
            })
        
        # Формируем XML
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
'''
        
        for url in urls:
            xml_content += f'''  <url>
    <loc>{request.scheme}://{request.get_host()}{url['loc']}</loc>
'''
            if 'lastmod' in url:
                xml_content += f'''    <lastmod>{url['lastmod']}</lastmod>
'''
            xml_content += f'''    <priority>{url['priority']}</priority>
  </url>
'''
        
        xml_content += '</urlset>'
        
        return HttpResponse(xml_content, content_type='application/xml')
        
    except Exception as e:
        logger.error(f"Ошибка генерации sitemap: {str(e)}", exc_info=True)
        return HttpResponse(status=500)

# ---------- error handlers ----------

def handler404(request, exception):
    """Обработчик 404 ошибки"""
    return render(request, '404.html', status=404)

def handler500(request):
    """Обработчик 500 ошибки"""
    return render(request, '500.html', status=500)