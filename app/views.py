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

logger = logging.getLogger(__name__)

# Константы
CACHE_VERSION = 1
ALLOWED_STATUSES = {"success", "failed", "pending"}

def _has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except FieldDoesNotExist:
        return False

def public_storage_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    bucket = os.environ.get("SUPABASE_BUCKET", "media").strip("/")
    if not base:
        base = "https://pyttzlcuxyfkhrwggrwi.supabase.co"
    return f"{base}/storage/v1/object/public/{bucket}/{path.lstrip('/')}"

def first_nonempty(*vals):
    for v in vals:
        if v:
            return v
    return None

def user_has_course_access(user, course):
    """Проверяет, имеет ли пользователь доступ к курсу."""
    if not user.is_authenticated:
        return False
    if not course.price or float(course.price or 0) == 0:
        return True
    return Enrollment.objects.filter(user=user, course=course).exists()

def article_card_dto(article, request=None):
    base_url = f"{settings.STATIC_URL}img/articles/article-placeholder.jpg"
    
    return {
        'id': article.id,
        'title': article.title,
        'slug': article.slug,
        'excerpt': article.excerpt or '',
        'created_at': article.created_at,
        'image_url': base_url,
        'url': reverse('article_detail', args=[article.slug]),
        'view_count': getattr(article, 'view_count', 0),
    }

def course_card_dto(course, request=None):
    base_url = f"{settings.STATIC_URL}img/courses/course-placeholder.jpg"
    
    return {
        'id': course.id,
        'title': course.title,
        'slug': course.slug,
        'price': float(course.price or 0),
        'short_description': course.short_description or '',
        'category': {
            'name': course.category.name if course.category else '',
            'slug': course.category.slug if course.category else '',
        },
        'students_count': getattr(course, 'students_count', 
                                course.enrollments.count() if hasattr(course, 'enrollments') else 0),
        'image_url': base_url,
        'url': reverse('course_detail', args=[course.slug]),
    }

@csrf_exempt
def kaspi_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=400)
    
    if request.content_type != "application/json":
        return JsonResponse({"error": "Invalid content type"}, status=400)

    signature = request.headers.get("X-Kaspi-Signature") or ""
    body = request.body
    secret = getattr(settings, "KASPI_SECRET", None)
    if not secret:
        logger.error("KASPI_SECRET is not set in settings")
        return JsonResponse({"error": "KASPI_SECRET is not set"}, status=500)

    try:
        expected_signature = hmac.new(
            key=secret.encode(), 
            msg=body, 
            digestmod=hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning(f"Invalid signature received: {signature}")
            return JsonResponse({"error": "Invalid signature"}, status=403)

        data = json.loads(body)
        invoice_id = data.get("invoiceId")
        status = data.get("status")
        amount = data.get("amount")
        
        if not invoice_id or not status:
            return JsonResponse({"error": "Missing required fields"}, status=400)
        
        if status not in ALLOWED_STATUSES:
            logger.warning(f"Invalid status received: {status}")
            return JsonResponse({"error": "Invalid status"}, status=400)
        
        payment = Payment.objects.get(kaspi_invoice_id=invoice_id)
        
        if amount is not None:
            try:
                amount_float = float(amount)
                payment_amount_float = float(payment.amount or 0)
                if amount_float < payment_amount_float:
                    logger.warning(f"Amount mismatch: {amount_float} < {payment_amount_float}")
                    return JsonResponse({"error": "Invalid amount"}, status=400)
            except (TypeError, ValueError):
                logger.error(f"Invalid amount format: {amount}")
                return JsonResponse({"error": "Invalid amount format"}, status=400)

        payment.status = status
        payment.save(update_fields=["status"])

        if status == "success":
            Enrollment.objects.get_or_create(user=payment.user, course=payment.course)
            payment.course.students.add(payment.user)
            logger.info(f"Payment {invoice_id} succeeded for user {payment.user.id}")

        return JsonResponse({"status": "ok"})
        
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for invoice: {invoice_id}")
        return JsonResponse({"error": "Payment not found"}, status=404)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook body")
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in kaspi_webhook: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Internal server error"}, status=500)

@csrf_protect
def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        
        if form.is_valid():
            try:
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
            except Exception as e:
                logger.error(f"Error during user registration: {str(e)}", exc_info=True)
                messages.error(request, "Произошла ошибка при создании аккаунта")
        else:
            if 'captcha' in form.errors:
                messages.error(request, "Пожалуйста, пройдите проверку reCAPTCHA.")
            else:
                messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = CustomUserCreationForm()
    
    return render(request, "registration/signup.html", {"form": form})

def home(request):
    language = get_language() or 'ru'
    cache_key = f'home_page_v{CACHE_VERSION}_{language}'
    cached_data = cache.get(cache_key)
    
    if cached_data and not request.user.is_authenticated:
        return render(request, "home.html", cached_data)
    
    try:
        featured_courses_qs = Course.objects.filter(
            status=Course.PUBLISHED,
            is_featured=True,
            is_deleted=False
        ).only(
            'id', 'title', 'slug', 'price', 'short_description', 'category_id'
        )[:6]
        
        popular_courses_qs = Course.objects.filter(
            status=Course.PUBLISHED,
            is_deleted=False
        ).annotate(
            students_count=Count('enrollments', distinct=True)
        ).only(
            'id', 'title', 'slug', 'price', 'short_description'
        ).order_by('-students_count', '-created_at')[:6]
        
        reviews = list(Review.objects.filter(
            is_active=True,
            course__status=Course.PUBLISHED
        ).select_related('user', 'course').only(
            'rating', 'comment', 'created_at',
            'user__first_name', 'user__last_name',
            'course__title'
        )[:5].values(
            'rating', 'comment', 'created_at',
            'user__first_name', 'user__last_name',
            'course__title'
        ))
        
        latest_articles_qs = Article.objects.filter(
            status=Article.PUBLISHED
        ).only(
            'id', 'title', 'slug', 'excerpt', 'created_at'
        ).order_by('-created_at')[:3]
        
        featured_courses = [course_card_dto(course) for course in featured_courses_qs]
        popular_courses = [course_card_dto(course) for course in popular_courses_qs]
        latest_articles = [article_card_dto(article) for article in latest_articles_qs]
        
        categories = []
        
    except DatabaseError as e:
        logger.error(f"Database error loading home data: {str(e)}", exc_info=True)
        featured_courses = []
        popular_courses = []
        categories = []
        reviews = []
        latest_articles = []
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading home data: {str(e)}", exc_info=True)
        featured_courses = []
        popular_courses = []
        categories = []
        reviews = []
        latest_articles = []

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
    
    if not request.user.is_authenticated:
        cache.set(cache_key, context, 180)
    
    return render(request, "home.html", context)

@login_required
def toggle_wishlist(request, slug):
    try:
        course = Course.objects.get(slug=slug)
        wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, course=course)

        if created:
            message = "Курс добавлен в избранное"
            in_wishlist = True
        else:
            wishlist_item.delete()
            message = "Курс удален из избранного"
            in_wishlist = False

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True, "in_wishlist": in_wishlist, "message": message})

        messages.success(request, message)
        return redirect("course_detail", slug=slug)
        
    except Course.DoesNotExist:
        messages.error(request, "Курс не найден")
        return redirect("courses_list")
    except Exception as e:
        logger.error(f"Error toggling wishlist: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка")
        return redirect("courses_list")

def catalog(request):
    return redirect('courses_list')

def category_detail(request, slug):
    try:
        category = Category.objects.get(slug=slug, is_active=True)
        
        courses_qs = Course.objects.filter(
            category=category,
            status=Course.PUBLISHED,
            is_deleted=False
        ).select_related("category").only(
            'id', 'title', 'slug', 'price', 'short_description',
            'created_at'
        ).order_by('-created_at')
        
        paginator = Paginator(courses_qs, 12)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        
        courses_with_images = [course_card_dto(course) for course in page_obj]
        
        context = {
            "category": category,
            "courses": courses_with_images,
            "is_paginated": page_obj.has_other_pages(),
            "page_obj": page_obj,
        }
        
    except Category.DoesNotExist:
        raise Http404("Категория не найдена")
    except DatabaseError as e:
        logger.error(f"Database error loading category {slug}: {str(e)}", exc_info=True)
        raise Http404("Категория не найдена")
    except Exception as e:
        logger.error(f"Error loading category {slug}: {str(e)}", exc_info=True)
        raise Http404("Категория не найдена")
    
    return render(request, "categories/detail.html", context)

def courses_list(request):
    search_query = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "newest")
    price_filter = request.GET.get("price")
    category_filter = request.GET.get("category")
    
    params = f"{search_query}_{sort_by}_{price_filter}_{category_filter}"
    params_hash = hashlib.md5(params.encode()).hexdigest()[:8]
    cache_key = f'courses_list_v{CACHE_VERSION}_{params_hash}'
    
    if not request.user.is_authenticated:
        cached_data = cache.get(cache_key)
        if cached_data:
            return render(request, "courses/list.html", cached_data)
    
    try:
        courses_qs = Course.objects.filter(
            status=Course.PUBLISHED,
            is_deleted=False
        ).select_related("category").only(
            'id', 'title', 'slug', 'price', 'short_description',
            'created_at', 'category_id',
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

        if sort_by == "popular":
            courses_qs = courses_qs.annotate(
                students_count=Count('enrollments', distinct=True)
            ).order_by("-students_count", "-created_at")
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

        courses_with_images = [course_card_dto(course) for course in page_obj]

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
        
        if not request.user.is_authenticated:
            cache.set(cache_key, context, 300)
    
    except DatabaseError as e:
        logger.error(f"Database error loading courses list: {str(e)}", exc_info=True)
        context = {
            "courses": [],
            "categories": [],
            "is_paginated": False,
            "page_obj": None,
            "q": search_query,
            "sort_by": sort_by,
        }
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading courses list: {str(e)}", exc_info=True)
        context = {
            "courses": [],
            "categories": [],
            "is_paginated": False,
            "page_obj": None,
            "q": search_query,
            "sort_by": sort_by,
        }
    
    return render(request, "courses/list.html", context)

def articles_list(request):
    try:
        articles_qs = Article.objects.filter(
            status='published'
        ).order_by('-created_at')

        articles_dto = [article_card_dto(article) for article in articles_qs]
        
        featured_article = articles_dto[0] if articles_dto else None
        rest_articles = articles_dto[1:] if len(articles_dto) > 1 else []

        context = {
            "articles": articles_dto,
            "featured_article": featured_article,
            "rest_articles": rest_articles,
        }
        
    except DatabaseError as e:
        logger.error(f"Database error loading articles list: {str(e)}", exc_info=True)
        context = {
            "articles": [],
            "featured_article": None,
            "rest_articles": [],
        }
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading articles list: {str(e)}", exc_info=True)
        context = {
            "articles": [],
            "featured_article": None,
            "rest_articles": [],
        }
    
    return render(request, "articles/list.html", context)

def article_detail(request, slug):
    cache_key = f'article_detail_v{CACHE_VERSION}_{slug}'
    
    if not request.user.is_authenticated:
        cached_data = cache.get(cache_key)
        if cached_data:
            return render(request, "articles/detail.html", cached_data)
    
    try:
        article_obj = Article.objects.filter(
            slug=slug,
            status=Article.PUBLISHED
        ).only(
            'id', 'title', 'slug', 'body', 'excerpt', 'created_at'
        ).order_by('id').first()
        
        if not article_obj:
            raise Http404("Статья не найдена")
        
        article_data = article_card_dto(article_obj)
        article_data.update({
            'body': article_obj.body or "",
        })
        
        latest_qs = Article.objects.filter(
            status=Article.PUBLISHED
        ).exclude(
            pk=article_obj.pk
        ).only(
            'id', 'title', 'slug', 'created_at'
        ).order_by('-created_at')[:4]
        
        latest_articles = [article_card_dto(article) for article in latest_qs]
        
        context = {
            "article": article_data,
            "latest": latest_articles
        }
        
        if not request.user.is_authenticated:
            cache.set(cache_key, context, 900)
        
    except Article.DoesNotExist:
        raise Http404("Статья не найдена")
    except DatabaseError as e:
        logger.error(f"Database error loading article {slug}: {str(e)}", exc_info=True)
        raise Http404("Статья не найдена")
    except Exception as e:
        logger.error(f"Error loading article {slug}: {str(e)}", exc_info=True)
        raise Http404("Статья не найдена")
    
    return render(request, "articles/detail.html", context)

def materials_list(request):
    cache_key = f'materials_list_v{CACHE_VERSION}_all'
    
    if not request.user.is_authenticated:
        cached_data = cache.get(cache_key)
        if cached_data:
            return render(request, "materials/list.html", cached_data)
    
    try:
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
        
        if not request.user.is_authenticated:
            cache.set(cache_key, context, 900)
    
    except DatabaseError as e:
        logger.error(f"Database error loading materials list: {str(e)}", exc_info=True)
        context = {"materials": []}
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading materials list: {str(e)}", exc_info=True)
        context = {"materials": []}
    
    return render(request, "materials/list.html", context)

def course_detail(request, slug):
    cache_key = f'course_detail_v{CACHE_VERSION}_{slug}'
    
    if not request.user.is_authenticated:
        cached_data = cache.get(cache_key)
        if cached_data:
            if request.user.is_authenticated:
                cached_data = _enrich_course_data(cached_data, request.user)
            return render(request, "courses/detail.html", cached_data)
    
    try:
        course_obj = Course.objects.filter(
            slug=slug,
            status=Course.PUBLISHED,
            is_deleted=False
        ).select_related("category", "instructor").only(
            'id', 'title', 'slug', 'price', 'short_description', 'description',
            'category_id', 'category__name', 'category__slug',
            'instructor_id', 'instructor__first_name', 'instructor__last_name',
            'created_at'
        ).order_by('id').first()
        
        if not course_obj:
            raise Http404("Курс не найден")
        
        course_data = course_card_dto(course_obj)
        course_data.update({
            'description': course_obj.description or "",
            'instructor': {
                'name': f"{course_obj.instructor.first_name or ''} {course_obj.instructor.last_name or ''}".strip() if course_obj.instructor else "",
            },
        })

        has_access = False
        is_in_wishlist = False
        if request.user.is_authenticated:
            has_access = user_has_course_access(request.user, course_obj)
            is_in_wishlist = Wishlist.objects.filter(
                user=request.user, 
                course=course_obj
            ).exists()

        try:
            modules = list(Module.objects.filter(
                course=course_obj, 
                is_active=True
            ).only(
                'id', 'title', 'order', 'is_active'
            ).order_by("order")[:20])
        except Exception:
            modules = []

        related_courses_qs = Course.objects.filter(
            category=course_obj.category,
            status=Course.PUBLISHED,
            is_deleted=False
        ).exclude(id=course_obj.id).only(
            'id', 'title', 'slug', 'price', 'short_description'
        )[:4]
        
        related_courses = [course_card_dto(course) for course in related_courses_qs]

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
        
        if not request.user.is_authenticated:
            cache.set(cache_key, context, 600)
        
    except Course.DoesNotExist:
        raise Http404("Курс не найден")
    except DatabaseError as e:
        logger.error(f"Database error loading course {slug}: {str(e)}", exc_info=True)
        raise Http404("Курс не найден")
    except Exception as e:
        logger.error(f"Error loading course {slug}: {str(e)}", exc_info=True)
        raise Http404("Курс не найден")
    
    return render(request, "courses/detail.html", context)

def _enrich_course_data(cached_data, user):
    if not user.is_authenticated:
        return cached_data
    
    result = cached_data.copy()
    
    try:
        course_id = result['course'].get('id')
        if course_id:
            has_access = Enrollment.objects.filter(
                user=user, 
                course_id=course_id
            ).exists()
            result['has_access'] = has_access
            
            is_in_wishlist = Wishlist.objects.filter(
                user=user, 
                course_id=course_id
            ).exists()
            result['is_in_wishlist'] = is_in_wishlist
            
    except Exception as e:
        logger.error(f"Error enriching course data: {str(e)}", exc_info=True)
    
    return result

def course_learn(request, course_slug):
    try:
        course_obj = Course.objects.filter(
            slug=course_slug,
            status=Course.PUBLISHED,
            is_deleted=False
        ).only('id', 'title', 'slug', 'price').order_by('id').first()
        
        if not course_obj:
            raise Http404("Курс не найден")
        
        if not request.user.is_authenticated:
            messages.error(request, "Для доступа к курсу необходимо авторизоваться")
            return redirect('login')
        
        if not user_has_course_access(request.user, course_obj):
            messages.error(request, "У вас нет доступа к этому курсу")
            return redirect("course_detail", slug=course_slug)
        
        first_lesson = Lesson.objects.filter(
            module__course=course_obj,
            is_active=True
        ).order_by("module__order", "order").first()
        
        if first_lesson:
            return redirect("lesson_view", course_slug=course_slug, lesson_slug=first_lesson.slug)
        
        messages.info(request, "В курсе пока нет уроков")
        return redirect("course_detail", slug=course_slug)
        
    except Course.DoesNotExist:
        raise Http404("Курс не найден")
    except DatabaseError as e:
        logger.error(f"Database error loading course for learning {course_slug}: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return redirect("course_detail", slug=course_slug)
    except Exception as e:
        logger.error(f"Error loading course for learning {course_slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке курса")
        return redirect("course_detail", slug=course_slug)

def lesson_view(request, course_slug, lesson_slug):
    return lesson_detail(request, course_slug, lesson_slug)

@login_required
def lesson_detail(request, course_slug, lesson_slug):
    try:
        course_obj = Course.objects.filter(
            slug=course_slug,
            status=Course.PUBLISHED,
            is_deleted=False
        ).only('id', 'title', 'slug', 'price').order_by('id').first()
        
        if not course_obj:
            raise Http404("Курс не найден")
        
        if not user_has_course_access(request.user, course_obj):
            messages.error(request, "У вас нет доступа к этому уроку")
            return redirect("course_detail", slug=course_slug)
        
        course_data = course_card_dto(course_obj)

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
                
        except Lesson.DoesNotExist:
            raise Http404("Урок не найден")
        except Exception:
            messages.error(request, "Урок недоступен")
            return redirect("course_detail", slug=course_slug)

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

        try:
            blocks = LessonBlock.objects.filter(lesson=lesson, is_deleted=False)
            if blocks.exists():
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
            logger.error(f"Error creating progress for lesson {lesson.id}: {str(e)}", exc_info=True)

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
    except DatabaseError as e:
        logger.error(f"Database error loading lesson {course_slug}/{lesson_slug}: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return redirect("courses_list")
    except Exception as e:
        logger.error(f"Error loading lesson {course_slug}/{lesson_slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке урока")
        return redirect("courses_list")

@login_required
def update_progress(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
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
        
        lesson = Lesson.objects.get(id=lesson_id)
        
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
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except DatabaseError as e:
        logger.error(f"Database error updating progress: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Database error"}, status=500)
    except Exception as e:
        logger.error(f"Error updating progress: {str(e)}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)

def _check_course_completion(user, course):
    try:
        required_blocks = LessonBlock.objects.filter(
            lesson__module__course=course,
            is_required=True,
            is_deleted=False
        ).count()
        
        if required_blocks == 0:
            return
        
        completed_blocks = BlockProgress.objects.filter(
            user=user,
            block__lesson__module__course=course,
            is_completed=True
        ).count()
        
        if completed_blocks >= required_blocks:
            enrollment = Enrollment.objects.get(user=user, course=course)
            if not enrollment.completed:
                enrollment.completed = True
                enrollment.completed_at = timezone.now()
                enrollment.save()
                
    except Enrollment.DoesNotExist:
        logger.warning(f"Enrollment not found for user {user.id} and course {course.id}")
    except Exception as e:
        logger.error(f"Error checking course completion: {str(e)}", exc_info=True)

@login_required
def enroll_course(request, slug):
    try:
        course = Course.objects.filter(
            slug=slug,
            status=Course.PUBLISHED,
            is_deleted=False
        ).only('id', 'slug', 'price').order_by('id').first()
        
        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")
        
        if not user_has_course_access(request.user, course):
            Enrollment.objects.get_or_create(user=request.user, course=course)
        
        first_lesson = Lesson.objects.filter(
            module__course=course,
            is_active=True
        ).order_by("module__order", "order").first()
        
        if first_lesson:
            return redirect("lesson_view", course_slug=course.slug, lesson_slug=first_lesson.slug)
        else:
            messages.success(request, "Вы успешно записались на курс!")
            return redirect("course_detail", slug=slug)
            
    except Course.DoesNotExist:
        messages.error(request, "Курс не найден")
        return redirect("courses_list")
    except DatabaseError as e:
        logger.error(f"Database error enrolling in course {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return redirect("course_detail", slug=slug)
    except Exception as e:
        logger.error(f"Error enrolling in course {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при записи на курс")
        return redirect("course_detail", slug=slug)

def checkout(request, slug):
    return create_payment(request, slug)

@login_required
def create_payment(request, slug):
    try:
        course = Course.objects.filter(
            slug=slug,
            status=Course.PUBLISHED,
            is_deleted=False
        ).only('id', 'title', 'slug', 'price', 'discount_price').order_by('id').first()
        
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
        
    except Course.DoesNotExist:
        messages.error(request, "Курс не найден")
        return redirect("courses_list")
    except DatabaseError as e:
        logger.error(f"Database error creating payment for {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return redirect("course_detail", slug=slug)
    except Exception as e:
        logger.error(f"Error creating payment for {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при создании платежа")
        return redirect("course_detail", slug=slug)

def checkout_confirm(request, slug):
    return payment_claim(request, slug)

@login_required
def payment_claim(request, slug):
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
        
    except Course.DoesNotExist:
        messages.error(request, "Курс не найден")
        return redirect("courses_list")
    except DatabaseError as e:
        logger.error(f"Database error confirming payment {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return redirect("course_detail", slug=slug)
    except Exception as e:
        logger.error(f"Error confirming payment {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка")
        return redirect("course_detail", slug=slug)

def payment_webhook(request):
    return kaspi_webhook(request)

@login_required
def payment_thanks(request, slug):
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
        
    except Course.DoesNotExist:
        messages.error(request, "Курс не найден")
        return redirect("courses_list")
    except Exception as e:
        logger.error(f"Error loading thanks page {slug}: {str(e)}", exc_info=True)
        return redirect("courses_list")

@login_required
def my_courses(request):
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
        
    except DatabaseError as e:
        logger.error(f"Database error loading my courses: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return render(request, "courses/my_courses.html", {
            "in_progress": [],
            "completed": [],
        })
    except Exception as e:
        logger.error(f"Error loading my courses: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке курсов")
        return render(request, "courses/my_courses.html", {
            "in_progress": [],
            "completed": [],
        })

@login_required
def dashboard(request):
    try:
        user = request.user
        
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

        completed_courses = Enrollment.objects.filter(
            user_id=user.id, 
            completed=True
        ).count()

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
        
    except DatabaseError as e:
        logger.error(f"Database error loading dashboard: {str(e)}", exc_info=True)
        context = {
            "total_courses": 0,
            "completed_courses": 0,
            "total_blocks": 0,
            "completed_blocks": 0,
            "recent_courses": [],
        }
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}", exc_info=True)
        context = {
            "total_courses": 0,
            "completed_courses": 0,
            "total_blocks": 0,
            "completed_blocks": 0,
            "recent_courses": [],
        }
    
    return render(request, "users/dashboard.html", context)

def learning_dashboard(request):
    return dashboard(request)

@login_required
def profile_settings(request):
    try:
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
    except DatabaseError as e:
        logger.error(f"Database error loading profile: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return redirect('dashboard')
    except Exception as e:
        logger.error(f"Error loading profile: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке профиля")
        return redirect('dashboard')
    
    user = request.user
    
    if request.method == 'POST':
        active_tab = 'profile'
        
        try:
            if 'update_profile' in request.POST:
                try:
                    first_name = request.POST.get('first_name', '').strip()
                    last_name = request.POST.get('last_name', '').strip()
                    
                    if first_name:
                        user.first_name = first_name
                    if last_name:
                        user.last_name = last_name
                    
                    if 'avatar' in request.FILES:
                        profile.avatar = request.FILES['avatar']
                    
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
                except DatabaseError as e:
                    logger.error(f"Database error updating profile: {str(e)}", exc_info=True)
                    messages.error(request, 'Временные проблемы с базой данных')
                except Exception as e:
                    logger.error(f"Error updating profile: {str(e)}", exc_info=True)
                    messages.error(request, 'Произошла ошибка при обновлении профиля')
                
                active_tab = 'profile'
            
            elif 'change_password' in request.POST:
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
                except DatabaseError as e:
                    logger.error(f"Database error changing password: {str(e)}", exc_info=True)
                    messages.error(request, 'Временные проблемы с базой данных')
                except Exception as e:
                    logger.error(f"Error changing password: {str(e)}", exc_info=True)
                    messages.error(request, 'Произошла ошибка при смене пароля')
                
                active_tab = 'security'
                
            elif 'update_notifications' in request.POST:
                try:
                    profile.email_notifications = 'email_notifications' in request.POST
                    profile.course_updates = 'course_updates' in request.POST
                    profile.newsletter = 'newsletter' in request.POST
                    profile.push_reminders = 'push_reminders' in request.POST
                    profile.save()
                    messages.success(request, 'Настройки уведомлений сохранены!')
                except DatabaseError as e:
                    logger.error(f"Database error updating notifications: {str(e)}", exc_info=True)
                    messages.error(request, 'Временные проблемы с базой данных')
                except Exception as e:
                    logger.error(f"Error updating notifications: {str(e)}", exc_info=True)
                    messages.error(request, 'Произошла ошибка при сохранении настроек уведомлений')
                
                active_tab = 'notifications'
            
            return redirect(f'{request.path}?tab={active_tab}')
            
        except Exception as e:
            logger.error(f"Error processing profile form: {str(e)}", exc_info=True)
            messages.error(request, 'Произошла ошибка при сохранении настроек')
    
    active_tab = request.GET.get('tab', 'profile')
    
    context = {
        'user': user,
        'profile': profile,
        'active_tab': active_tab,
    }
    
    return render(request, "users/profile_settings.html", context)

def account_settings(request):
    return profile_settings(request)

@login_required
def add_review(request, slug):
    try:
        course = Course.objects.filter(
            slug=slug,
            status=Course.PUBLISHED,
            is_deleted=False
        ).only('id', 'title', 'slug').order_by('id').first()
        
        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")

        if not user_has_course_access(request.user, course):
            messages.error(request, "Только студенты курса могут оставлять отзывы")
            return redirect("course_detail", slug=slug)

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
        
    except Course.DoesNotExist:
        messages.error(request, "Курс не найден")
        return redirect("courses_list")
    except DatabaseError as e:
        logger.error(f"Database error adding review {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return redirect("course_detail", slug=slug)
    except Exception as e:
        logger.error(f"Error adding review {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка")
        return redirect("course_detail", slug=slug)

@login_required
def instructor_dashboard(request):
    if not request.user.is_staff and not request.user.is_superuser:
        is_instructor = Course.objects.filter(instructor=request.user).exists() or \
                       CourseStaff.objects.filter(user=request.user, role__in=['owner', 'instructor']).exists()
        if not is_instructor:
            messages.error(request, "У вас нет прав доступа к панели инструктора")
            return redirect('learning_dashboard')
    
    try:
        user = request.user
        
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
        
    except DatabaseError as e:
        logger.error(f"Database error loading instructor dashboard: {str(e)}", exc_info=True)
        context = {
            'courses': [],
            'total_courses': 0,
            'total_students': 0,
            'total_revenue': 0,
        }
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading instructor dashboard: {str(e)}", exc_info=True)
        context = {
            'courses': [],
            'total_courses': 0,
            'total_students': 0,
            'total_revenue': 0,
        }
    
    return render(request, "instructor/dashboard.html", context)

@login_required
def instructor_courses(request):
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
            'created_at'
        ).order_by('-created_at')
        
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
        
    except DatabaseError as e:
        logger.error(f"Database error loading instructor courses: {str(e)}", exc_info=True)
        context = {
            'courses': [],
        }
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading instructor courses: {str(e)}", exc_info=True)
        context = {
            'courses': [],
        }
    
    return render(request, "instructor/courses.html", context)

@login_required
def instructor_course_detail(request, slug):
    try:
        course = Course.objects.get(slug=slug)
        
        has_access = (
            request.user.is_staff or 
            request.user.is_superuser or
            course.instructor == request.user or
            CourseStaff.objects.filter(course=course, user=request.user, role__in=['owner', 'instructor']).exists()
        )
        
        if not has_access:
            messages.error(request, "У вас нет прав доступа к этому курсу")
            return redirect('instructor_courses')
        
        enrollments = Enrollment.objects.filter(course=course)
        payments = Payment.objects.filter(course=course, status='success')
        reviews = Review.objects.filter(course=course, is_active=True)
        
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
    except DatabaseError as e:
        logger.error(f"Database error loading instructor course details {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return redirect('instructor_courses')
    except Exception as e:
        logger.error(f"Error loading instructor course details {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке данных курса")
        return redirect('instructor_courses')
    
    return render(request, "instructor/course_detail.html", context)

@login_required
def instructor_analytics(request):
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
        ).distinct()
        
        total_courses = courses.count()
        total_enrollments = Enrollment.objects.filter(course__in=courses).count()
        total_revenue = Payment.objects.filter(course__in=courses, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        total_reviews = Review.objects.filter(course__in=courses, is_active=True).count()
        
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
        
    except DatabaseError as e:
        logger.error(f"Database error loading instructor analytics: {str(e)}", exc_info=True)
        context = {
            'total_courses': 0,
            'total_enrollments': 0,
            'total_revenue': 0,
            'total_reviews': 0,
            'months_data': [],
        }
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading instructor analytics: {str(e)}", exc_info=True)
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
        ).distinct()
        
        students = User.objects.filter(
            enrollments__course__in=courses
        ).distinct().select_related('profile').prefetch_related(
            'enrollments', 'enrollments__course'
        )[:50]
        
        students_data = []
        for student in students:
            student_courses = Enrollment.objects.filter(
                user=student,
                course__in=courses
            ).select_related('course')[:5]
            
            courses_list = []
            for enrollment in student_courses:
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
        
    except DatabaseError as e:
        logger.error(f"Database error loading instructor students: {str(e)}", exc_info=True)
        context = {
            'students': [],
        }
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading instructor students: {str(e)}", exc_info=True)
        context = {
            'students': [],
        }
    
    return render(request, "instructor/students.html", context)

def api_courses(request):
    try:
        courses = Course.objects.filter(
            status=Course.PUBLISHED,
            is_deleted=False
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
        
    except DatabaseError as e:
        logger.error(f"Database error in API courses: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Database error',
        }, status=500)
    except Exception as e:
        logger.error(f"Error in API courses: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error',
        }, status=500)

@login_required
def api_enroll(request):
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
            status=Course.PUBLISHED,
            is_deleted=False
        ).first()
        
        if not course:
            return JsonResponse({
                'status': 'error',
                'message': 'Course not found',
            }, status=404)
        
        if Enrollment.objects.filter(user=request.user, course=course).exists():
            return JsonResponse({
                'status': 'success',
                'message': 'Already enrolled',
                'enrolled': True,
            })
        
        Enrollment.objects.create(user=request.user, course=course)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Successfully enrolled',
            'enrolled': True,
        })
        
    except DatabaseError as e:
        logger.error(f"Database error in API enroll: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Database error',
        }, status=500)
    except Exception as e:
        logger.error(f"Error in API enroll: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error',
        }, status=500)

def api_reviews(request):
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
        
    except DatabaseError as e:
        logger.error(f"Database error in API reviews: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Database error',
        }, status=500)
    except Exception as e:
        logger.error(f"Error in API reviews: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error',
        }, status=500)

@login_required
def crm_dashboard(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "У вас нет прав доступа к CRM")
        return redirect('learning_dashboard')
    
    try:
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        new_leads_today = Lead.objects.filter(created_at__date=today).count()
        new_leads_week = Lead.objects.filter(created_at__gte=week_ago).count()
        new_leads_month = Lead.objects.filter(created_at__gte=month_ago).count()
        
        converted_leads_today = Lead.objects.filter(converted=True, converted_at__date=today).count()
        converted_leads_week = Lead.objects.filter(converted=True, converted_at__gte=week_ago).count()
        converted_leads_month = Lead.objects.filter(converted=True, converted_at__gte=month_ago).count()
        
        payments_today = Payment.objects.filter(created_at__date=today, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        payments_week = Payment.objects.filter(created_at__gte=week_ago, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        payments_month = Payment.objects.filter(created_at__gte=month_ago, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        
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
        
    except DatabaseError as e:
        logger.error(f"Database error loading CRM dashboard: {str(e)}", exc_info=True)
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
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading CRM dashboard: {str(e)}", exc_info=True)
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
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "У вас нет прав доступа к CRM")
        return redirect('learning_dashboard')
    
    try:
        leads = Lead.objects.all().select_related('assigned_to').order_by('-created_at')
        
        status_filter = request.GET.get('status')
        if status_filter:
            leads = leads.filter(status=status_filter)
        
        search_query = request.GET.get('q')
        if search_query:
            leads = leads.filter(
                Q(email__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(phone__icontains=search_query)
            )
        
        paginator = Paginator(leads, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'leads': page_obj,
            'status_filter': status_filter,
            'search_query': search_query or '',
        }
        
    except DatabaseError as e:
        logger.error(f"Database error loading CRM leads: {str(e)}", exc_info=True)
        context = {
            'leads': [],
            'status_filter': '',
            'search_query': '',
        }
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading CRM leads: {str(e)}", exc_info=True)
        context = {
            'leads': [],
            'status_filter': '',
            'search_query': '',
        }
    
    return render(request, "crm/leads.html", context)

@login_required
def crm_payments(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "У вас нет прав доступа к CRM")
        return redirect('learning_dashboard')
    
    try:
        payments = Payment.objects.all().select_related('user', 'course').order_by('-created_at')
        
        status_filter = request.GET.get('status')
        if status_filter:
            payments = payments.filter(status=status_filter)
        
        search_query = request.GET.get('q')
        if search_query:
            payments = payments.filter(
                Q(user__username__icontains=search_query) |
                Q(user__email__icontains=search_query) |
                Q(course__title__icontains=search_query) |
                Q(payment_id__icontains=search_query)
            )
        
        paginator = Paginator(payments, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
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
        
    except DatabaseError as e:
        logger.error(f"Database error loading CRM payments: {str(e)}", exc_info=True)
        context = {
            'payments': [],
            'status_filter': '',
            'search_query': '',
            'total_revenue': 0,
            'pending_payments': 0,
            'failed_payments': 0,
        }
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading CRM payments: {str(e)}", exc_info=True)
        context = {
            'payments': [],
            'status_filter': '',
            'search_query': '',
            'total_revenue': 0,
            'pending_payments': 0,
            'failed_payments': 0,
        }
    
    return render(request, "crm/payments.html", context)

def about(request):
    cache_key = f'about_page_v{CACHE_VERSION}_data'
    
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
            "total_courses": Course.objects.filter(status=Course.PUBLISHED, is_deleted=False).count(),
            "total_students": Enrollment.objects.values('user').distinct().count(),
            "total_instructors": total_instructors,
        }
        
    except DatabaseError as e:
        logger.error(f"Database error loading about page: {str(e)}", exc_info=True)
        instructors = []
        stats = {"total_courses": 0, "total_students": 0, "total_instructors": 0}
        messages.error(request, "Временные проблемы с базой данных")
    except Exception as e:
        logger.error(f"Error loading about page: {str(e)}", exc_info=True)
        instructors = []
        stats = {"total_courses": 0, "total_students": 0, "total_instructors": 0}

    context = {
        "instructors": instructors,
        "stats": stats,
    }
    
    cache.set(cache_key, context, 1800)
    
    return render(request, "about.html", context)

def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Ваше сообщение успешно отправлено!")
            except DatabaseError as e:
                logger.error(f"Database error saving contact: {str(e)}", exc_info=True)
                messages.error(request, "Временные проблемы с базой данных")
            except Exception as e:
                logger.error(f"Error saving contact: {str(e)}", exc_info=True)
                messages.error(request, "Произошла ошибка при отправке сообщения")
            return redirect("contact")
    else:
        form = ContactForm()
    
    return render(request, "contact.html", {"form": form})

def design_wireframe(request):
    cache_key = f'design_wireframe_v{CACHE_VERSION}_data'
    
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
    
    cache.set(cache_key, context, 3600)
    
    return render(request, "design_wireframe.html", context)

def health_check(request):
    try:
        Course.objects.count()
        
        cache.set('health_check', 'ok', 1)
        if cache.get('health_check') != 'ok':
            raise Exception("Cache not working")
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'database': 'ok',
            'cache': 'ok',
        })
        
    except DatabaseError as e:
        logger.error(f"Database health check failed: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'error': 'Database error',
        }, status=500)
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'error': str(e),
        }, status=500)

def sitemap(request):
    try:
        urls = [
            {'loc': reverse('home'), 'priority': '1.0'},
            {'loc': reverse('about'), 'priority': '0.8'},
            {'loc': reverse('contact'), 'priority': '0.8'},
            {'loc': reverse('courses_list'), 'priority': '0.9'},
            {'loc': reverse('articles_list'), 'priority': '0.7'},
            {'loc': reverse('materials_list'), 'priority': '0.7'},
        ]
        
        courses = Course.objects.filter(
            status=Course.PUBLISHED, 
            is_deleted=False
        ).only('slug', 'updated_at')[:1000]
        
        for course in courses:
            urls.append({
                'loc': reverse('course_detail', args=[course.slug]),
                'lastmod': course.updated_at.strftime('%Y-%m-%d'),
                'priority': '0.8',
            })
        
        articles = Article.objects.filter(
            status=Article.PUBLISHED
        ).only('slug', 'updated_at')[:1000]
        
        for article in articles:
            urls.append({
                'loc': reverse('article_detail', args=[article.slug]),
                'lastmod': article.updated_at.strftime('%Y-%m-%d'),
                'priority': '0.6',
            })
        
        categories = Category.objects.filter(is_active=True).only('slug', 'updated_at')[:100]
        for category in categories:
            urls.append({
                'loc': reverse('category_detail', args=[category.slug]),
                'lastmod': category.updated_at.strftime('%Y-%m-%d'),
                'priority': '0.5',
            })
        
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
'''
        articles_list
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
        
    except DatabaseError as e:
        logger.error(f"Database error generating sitemap: {str(e)}", exc_info=True)
        return HttpResponse(status=500)
    except Exception as e:
        logger.error(f"Error generating sitemap: {str(e)}", exc_info=True)
        return HttpResponse(status=500)

def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)