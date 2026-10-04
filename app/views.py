from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.core.cache import cache
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.db import DatabaseError, ProgrammingError, transaction
from django.db.models import Q, Avg, Count, Sum, Max, Prefetch
from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.http import url_has_allowed_host_and_scheme

import hmac
import hashlib
import json
import os
import logging
import uuid
from typing import Optional
from datetime import timedelta

from .forms import (
    ContactForm,
    CustomUserCreationForm,
    ReviewForm,
    CorporateOrderRequestForm,
    CorporateParticipantsForm,
)
from .certificate_sync import CertificateRegistryError, sync_certificate_request
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
    Quiz, Question, Answer, QuizAttempt, Assignment, Submission, Certificate, CertificateRequest,
    Lead, Interaction, Segment, SupportTicket, FAQ,
    Plan, Subscription, Refund, Mailing,
    CourseStaff, AuditLog,
    Organization, CorporateOrder, CorporateInvitation
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
    """Доступ существует только через явное зачисление на курс."""
    if not user.is_authenticated:
        return False
    return Enrollment.objects.filter(
        user=user,
        course=course,
        is_deleted=False,
    ).exists()

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
    secret = (
        getattr(settings, "KASPI_WEBHOOK_SECRET", "")
        or getattr(settings, "KASPI_SECRET", "")
    )
    if not secret:
        logger.error("Kaspi webhook secret is not configured")
        return JsonResponse({"error": "Webhook is not configured"}, status=503)

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
    next_url = request.POST.get("next") or request.GET.get("next") or ""

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
                    if next_url and url_has_allowed_host_and_scheme(
                        next_url,
                        allowed_hosts={request.get_host()},
                        require_https=request.is_secure(),
                    ):
                        return redirect(next_url)
                    return redirect("home")
                messages.warning(request, "Аккаунт создан, но автологин не сработал. Войдите вручную.")
                return redirect("login")
            except Exception as e:
                logger.error(f"Error during user registration: {str(e)}", exc_info=True)
                messages.error(request, "Произошла ошибка при создании аккаунта")
        else:
            if "captcha" in form.errors:
                messages.error(request, "Пожалуйста, пройдите проверку reCAPTCHA.")
            else:
                messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = CustomUserCreationForm(initial={
            "email": request.GET.get("email", ""),
        })

    return render(request, "registration/signup.html", {
        "form": form,
        "next": next_url,
    })

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
    try:
        course_obj = get_object_or_404(
            Course.objects.select_related("category", "instructor"),
            slug=slug,
            status=Course.PUBLISHED,
            is_deleted=False,
        )

        lesson_qs = Lesson.objects.filter(
            is_active=True,
            is_deleted=False,
        ).order_by("order", "id")

        modules = list(
            Module.objects.filter(
                course=course_obj,
                is_active=True,
                is_deleted=False,
            ).prefetch_related(
                Prefetch("lessons", queryset=lesson_qs)
            ).order_by("order", "id")
        )

        lessons = []
        for module in modules:
            module_lessons = list(module.lessons.all())
            module.total_duration = sum((lesson.duration_minutes or 0) for lesson in module_lessons)
            lessons.extend(module_lessons)

        first_lesson = lessons[0] if lessons else None

        has_access = user_has_course_access(request.user, course_obj)
        is_in_wishlist = (
            request.user.is_authenticated
            and Wishlist.objects.filter(user=request.user, course=course_obj).exists()
        )

        teacher_profile = None
        if course_obj.instructor_id:
            teacher_profile = InstructorProfile.objects.filter(
                user_id=course_obj.instructor_id,
                is_deleted=False,
            ).first()

        reviews = Review.objects.filter(
            course=course_obj,
            is_active=True,
        ).select_related("user").order_by("-created_at")[:10]

        related_courses = Course.objects.filter(
            category=course_obj.category,
            status=Course.PUBLISHED,
            is_deleted=False,
        ).exclude(id=course_obj.id).select_related("category")[:4]

        return render(request, "courses/detail.html", {
            "course": course_obj,
            "has_access": has_access,
            "is_in_wishlist": is_in_wishlist,
            "modules": modules,
            "lessons": lessons,
            "first_lesson": first_lesson,
            "teacher_profile": teacher_profile,
            "reviews": reviews,
            "related_courses": related_courses,
        })

    except DatabaseError as e:
        logger.error(f"Database error loading course {slug}: {str(e)}", exc_info=True)
        raise Http404("Курс временно недоступен")

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
    course_obj = get_object_or_404(
        Course,
        slug=course_slug,
        status=Course.PUBLISHED,
        is_deleted=False,
    )

    if not user_has_course_access(request.user, course_obj):
        messages.error(request, "У вас нет доступа к этому уроку")
        return redirect("course_detail", slug=course_slug)

    lesson = get_object_or_404(
        Lesson.objects.select_related("module"),
        slug=lesson_slug,
        module__course=course_obj,
        is_active=True,
        is_deleted=False,
    )

    lessons_list = list(
        Lesson.objects.filter(
            module__course=course_obj,
            is_active=True,
            is_deleted=False,
        ).select_related("module").order_by("module__order", "order", "id")
    )
    current_index = next((i for i, item in enumerate(lessons_list) if item.id == lesson.id), 0)
    previous_lesson = lessons_list[current_index - 1] if current_index > 0 else None
    next_lesson = lessons_list[current_index + 1] if current_index < len(lessons_list) - 1 else None

    blocks = list(
        LessonBlock.objects.filter(
            lesson=lesson,
            is_deleted=False,
        ).select_related("quiz", "assignment").prefetch_related(
            "quiz__questions__answers"
        ).order_by("order", "id")
    )

    block_progress = {
        p.block_id: p
        for p in BlockProgress.objects.filter(user=request.user, block__in=blocks)
    }
    for block in blocks:
        if block.id not in block_progress:
            block_progress[block.id] = BlockProgress.objects.create(
                user=request.user,
                block=block,
                progress_percent=0,
                is_completed=False,
            )

    quiz_ids = [block.quiz_id for block in blocks if block.quiz_id]
    best_scores = {}
    if quiz_ids:
        attempts = QuizAttempt.objects.filter(
            user=request.user,
            quiz_id__in=quiz_ids,
        ).order_by("quiz_id", "-score_percent", "-completed_at")
        for attempt in attempts:
            best_scores.setdefault(attempt.quiz_id, attempt.score_percent)

    practical_responses = {
        response.block_id: response
        for response in PracticalResponse.objects.filter(
            user=request.user,
            block__in=blocks,
        )
    }

    for block in blocks:
        block.user_progress = block_progress.get(block.id)
        block.best_score = best_scores.get(block.quiz_id, 0) if block.quiz_id else 0
        block.practical_response = practical_responses.get(block.id)

    enrollment = Enrollment.objects.filter(user=request.user, course=course_obj).first()

    completion_status = _course_completion_status(request.user, course_obj)
    course_progress = completion_status["course_progress"]

    return render(request, "courses/lesson_detail.html", {
        "course": course_obj,
        "lesson": lesson,
        "blocks": blocks,
        "block_progress": block_progress,
        "best_scores": best_scores,
        "prev_lesson": previous_lesson,
        "next_lesson": next_lesson,
        "enrollment": enrollment,
        "course_progress": course_progress,
        "cumulative_score": completion_status["cumulative_score"],
        "quiz_count": completion_status["quiz_count"],
        "all_quizzes_passed": completion_status["all_quizzes_passed"],
    })


@login_required
def submit_quiz(request, quiz_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    quiz = get_object_or_404(
        Quiz.objects.select_related("lesson__module__course"),
        id=quiz_id,
        is_active=True,
    )
    course_obj = quiz.lesson.module.course

    if not user_has_course_access(request.user, course_obj):
        return JsonResponse({"error": "Нет доступа к курсу"}, status=403)

    previous_attempts = QuizAttempt.objects.filter(user=request.user, quiz=quiz)
    attempts_count = previous_attempts.count()
    if not quiz.unlimited_attempts and attempts_count >= quiz.attempts_allowed:
        return JsonResponse({
            "error": "Лимит попыток исчерпан",
            "attempts_used": attempts_count,
        }, status=400)

    questions = list(
        quiz.questions.prefetch_related("answers").order_by("order", "id")
    )
    points_total = sum(max(1, q.points) for q in questions)
    points_earned = 0
    answer_log = {}
    feedback = []

    for question in questions:
        field_name = f"question_{question.id}"
        submitted_values = request.POST.getlist(field_name)
        submitted_clean = [str(v).strip() for v in submitted_values if str(v).strip()]
        correct_answers = list(question.answers.filter(is_correct=True))

        is_correct = False
        if question.question_type == "multiple":
            correct_ids = {str(a.id) for a in correct_answers}
            is_correct = set(submitted_clean) == correct_ids
        elif question.question_type == "single":
            correct_ids = {str(a.id) for a in correct_answers}
            is_correct = len(submitted_clean) == 1 and submitted_clean[0] in correct_ids
        elif question.question_type == "text":
            expected = ""
            if correct_answers:
                expected = (correct_answers[0].correct_answer or correct_answers[0].text or "").strip()
            received = submitted_clean[0] if submitted_clean else ""
            is_correct = bool(expected) and received.casefold() == expected.casefold()

        if is_correct:
            points_earned += max(1, question.points)

        answer_log[str(question.id)] = {
            "submitted": submitted_clean,
            "correct": is_correct,
        }
        feedback.append({
            "question_id": question.id,
            "correct": is_correct,
            "explanation": question.explanation or "",
            "correct_answers": [answer.text for answer in correct_answers],
        })

    score_percent = round((points_earned / points_total) * 100) if points_total else 0
    attempt = QuizAttempt.objects.create(
        user=request.user,
        quiz=quiz,
        attempt_number=attempts_count + 1,
        score_percent=score_percent,
        points_earned=points_earned,
        points_total=points_total,
        answers=answer_log,
    )

    best_score = QuizAttempt.objects.filter(
        user=request.user,
        quiz=quiz,
    ).order_by("-score_percent", "-completed_at").values_list("score_percent", flat=True).first() or 0

    quiz_blocks = LessonBlock.objects.filter(
        quiz=quiz,
        lesson=quiz.lesson,
        is_deleted=False,
    )
    if attempt.passed:
        for block in quiz_blocks:
            BlockProgress.objects.update_or_create(
                user=request.user,
                block=block,
                defaults={
                    "progress_percent": 100,
                    "is_completed": True,
                    "completed_at": timezone.now(),
                },
            )

    _check_course_completion(request.user, course_obj)

    return JsonResponse({
        "success": True,
        "score": score_percent,
        "best_score": best_score,
        "passing_score": quiz.passing_score,
        "passed": attempt.passed,
        "attempt_number": attempt.attempt_number,
        "unlimited_attempts": quiz.unlimited_attempts,
        "feedback": feedback,
    })

@login_required
def complete_block(request, block_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    block = get_object_or_404(
        LessonBlock.objects.select_related("lesson__module__course", "quiz"),
        id=block_id,
        is_deleted=False,
    )
    course_obj = block.lesson.module.course
    if not user_has_course_access(request.user, course_obj):
        return JsonResponse({"error": "Нет доступа к курсу"}, status=403)

    if block.block_type == "quiz" and block.quiz_id:
        best_score = QuizAttempt.objects.filter(
            user=request.user,
            quiz=block.quiz,
        ).order_by("-score_percent").values_list("score_percent", flat=True).first() or 0
        if best_score < block.quiz.passing_score:
            return JsonResponse({
                "error": "Сначала пройдите тест",
                "best_score": best_score,
                "passing_score": block.quiz.passing_score,
            }, status=400)

    if block.block_type == "assignment" and block.is_required:
        if not PracticalResponse.objects.filter(
            user=request.user,
            block=block,
        ).exists():
            return JsonResponse({
                "error": "Сначала отправьте ответ на практическое задание."
            }, status=400)

    progress, _ = BlockProgress.objects.update_or_create(
        user=request.user,
        block=block,
        defaults={
            "progress_percent": 100,
            "is_completed": True,
            "completed_at": timezone.now(),
        },
    )
    _check_course_completion(request.user, course_obj)

    return JsonResponse({
        "success": True,
        "block_id": block.id,
        "progress": progress.progress_percent,
    })


@login_required
def submit_practical_response(request, block_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    block = get_object_or_404(
        LessonBlock.objects.select_related("lesson__module__course"),
        id=block_id,
        block_type="assignment",
        is_deleted=False,
    )
    course_obj = block.lesson.module.course
    if not user_has_course_access(request.user, course_obj):
        return JsonResponse({"error": "Нет доступа к курсу"}, status=403)

    text_value = (request.POST.get("text") or "").strip()
    if not text_value:
        return JsonResponse(
            {"error": "Введите ответ на практическое задание."},
            status=400,
        )

    response, _ = PracticalResponse.objects.update_or_create(
        user=request.user,
        block=block,
        defaults={"text": text_value},
    )

    progress, _ = BlockProgress.objects.update_or_create(
        user=request.user,
        block=block,
        defaults={
            "progress_percent": 100,
            "is_completed": True,
            "completed_at": timezone.now(),
        },
    )
    status = _check_course_completion(request.user, course_obj)

    return JsonResponse({
        "success": True,
        "block_id": block.id,
        "saved_at": response.updated_at.isoformat(),
        "progress": progress.progress_percent,
        "course_completed": bool(status and status["eligible_for_completion"]),
    })


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

def _course_completion_status(user, course):
    """Return one canonical completion calculation for progress and certificates."""
    required_blocks_qs = LessonBlock.objects.filter(
        lesson__module__course=course,
        lesson__is_active=True,
        lesson__is_deleted=False,
        is_required=True,
        is_deleted=False,
    )
    required_count = required_blocks_qs.count()
    completed_count = BlockProgress.objects.filter(
        user=user,
        block__in=required_blocks_qs,
        is_completed=True,
    ).count()

    quizzes = list(
        Quiz.objects.filter(
            blocks__in=required_blocks_qs.filter(block_type="quiz"),
            is_active=True,
        ).distinct().order_by("id")
    )
    quiz_ids = [quiz.id for quiz in quizzes]
    best_by_quiz = {}
    if quiz_ids:
        best_by_quiz = {
            row["quiz_id"]: row["best_score"] or 0
            for row in QuizAttempt.objects.filter(
                user=user,
                quiz_id__in=quiz_ids,
            ).values("quiz_id").annotate(best_score=Max("score_percent"))
        }

    scores = [int(best_by_quiz.get(quiz.id, 0)) for quiz in quizzes]
    cumulative_score = round(sum(scores) / len(scores)) if scores else 0
    all_quizzes_passed = all(
        best_by_quiz.get(quiz.id, 0) >= quiz.passing_score
        for quiz in quizzes
    ) if quizzes else True

    blocks_complete = required_count > 0 and completed_count >= required_count
    cumulative_passed = cumulative_score >= 80 if quizzes else True

    return {
        "required_count": required_count,
        "completed_count": completed_count,
        "course_progress": round((completed_count / required_count) * 100) if required_count else 0,
        "quiz_count": len(quizzes),
        "quiz_scores": best_by_quiz,
        "cumulative_score": cumulative_score,
        "all_quizzes_passed": all_quizzes_passed,
        "cumulative_passed": cumulative_passed,
        "eligible_for_completion": (
            blocks_complete
            and all_quizzes_passed
            and cumulative_passed
        ),
    }


def _check_course_completion(user, course):
    try:
        status = _course_completion_status(user, course)
        if not status["eligible_for_completion"]:
            return status

        enrollment = Enrollment.objects.get(user=user, course=course)
        if not enrollment.completed:
            enrollment.completed = True
            enrollment.completed_at = timezone.now()
            enrollment.save(update_fields=["completed", "completed_at", "updated_at"])
        return status

    except Enrollment.DoesNotExist:
        logger.warning(f"Enrollment not found for user {user.id} and course {course.id}")
        return None
    except Exception as e:
        logger.error(f"Error checking course completion: {str(e)}", exc_info=True)
        return None

@login_required
def enroll_course(request, slug):
    try:
        course = Course.objects.filter(
            slug=slug,
            status=Course.PUBLISHED,
            is_deleted=False
        ).only('id', 'slug', 'price', 'discount_price').order_by('id').first()

        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")

        if course.final_price and course.final_price > 0:
            if not user_has_course_access(request.user, course):
                messages.info(request, "Сначала необходимо оплатить курс.")
                return redirect("checkout", slug=course.slug)
        else:
            Enrollment.objects.get_or_create(user=request.user, course=course)

        first_lesson = Lesson.objects.filter(
            module__course=course,
            is_active=True,
            is_deleted=False,
        ).order_by("module__order", "order").first()

        if first_lesson:
            return redirect("lesson_view", course_slug=course.slug, lesson_slug=first_lesson.slug)

        messages.success(request, "Вы успешно записались на курс!")
        return redirect("course_detail", slug=slug)

    except DatabaseError as e:
        logger.error(f"Database error enrolling in course {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return redirect("course_detail", slug=slug)
    except Exception as e:
        logger.error(f"Error enrolling in course {slug}: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при записи на курс")
        return redirect("course_detail", slug=slug)

def _send_corporate_order_link(request, order):
    manage_url = request.build_absolute_uri(
        reverse("corporate_order_portal", args=[order.manage_token])
    )
    send_mail(
        subject=f"SkillsSpire: корпоративная заявка {order.order_number}",
        message=(
            f"Здравствуйте, {order.organization.contact_name}!\n\n"
            f"Заявка на курс «{order.course.title}» создана.\n"
            f"Количество мест: {order.seats_purchased}.\n"
            f"Корпоративная скидка: {order.discount_percent}%.\n"
            f"Сумма: {order.total_amount} ₸.\n\n"
            "По этой защищённой ссылке можно отслеживать статус заказа, "
            "а после подтверждения оплаты — распределить места между слушателями:\n"
            f"{manage_url}\n\nSkillsSpire"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.organization.contact_email],
        fail_silently=True,
    )
    return manage_url


def _send_corporate_invitation(request, invitation):
    invite_url = request.build_absolute_uri(
        reverse("corporate_invitation_accept", args=[invitation.token])
    )
    send_mail(
        subject=f"SkillsSpire: доступ к курсу «{invitation.order.course.title}»",
        message=(
            f"Здравствуйте, {invitation.first_name}!\n\n"
            f"Организация «{invitation.order.organization.name}» предоставила вам "
            f"индивидуальное место на курсе «{invitation.order.course.title}».\n\n"
            "Чтобы активировать доступ, откройте ссылку и войдите в SkillsSpire "
            "или создайте аккаунт с этим же email:\n"
            f"{invite_url}\n\n"
            f"Приглашение предназначено для: {invitation.email}\n"
            "Оплачивать курс повторно не нужно."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=True,
    )
    return invite_url


def corporate_order_request(request, slug):
    course_obj = get_object_or_404(
        Course,
        slug=slug,
        status=Course.PUBLISHED,
        is_deleted=False,
    )

    profile = None
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()

    initial = {}
    if request.user.is_authenticated:
        initial.update({
            "contact_name": request.user.get_full_name() or request.user.username,
            "contact_email": request.user.email,
            "contact_phone": profile.phone if profile else "",
            "organization_name": profile.company if profile else "",
        })

    if request.method == "POST":
        form = CorporateOrderRequestForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                organization, _ = Organization.objects.select_for_update().get_or_create(
                    bin=data["bin"],
                    defaults={
                        "name": data["organization_name"],
                        "legal_address": data["legal_address"],
                        "contact_name": data["contact_name"],
                        "contact_email": data["contact_email"],
                        "contact_phone": data["contact_phone"],
                    },
                )
                organization.name = data["organization_name"]
                organization.legal_address = data["legal_address"]
                organization.contact_name = data["contact_name"]
                organization.contact_email = data["contact_email"]
                organization.contact_phone = data["contact_phone"]
                organization.is_active = True
                organization.save()

                order = CorporateOrder.objects.create(
                    organization=organization,
                    course=course_obj,
                    requested_by=request.user if request.user.is_authenticated else None,
                    seats_purchased=data["seats"],
                    base_unit_price=course_obj.final_price or 0,
                    unit_price=course_obj.final_price or 0,
                    total_amount=0,
                    notes=data.get("note", ""),
                )

            _send_corporate_order_link(request, order)
            messages.success(
                request,
                "Корпоративная заявка создана. Ссылка на кабинет заказчика отправлена на указанный email."
            )
            return redirect("corporate_order_portal", token=order.manage_token)
    else:
        form = CorporateOrderRequestForm(initial=initial)

    tiers = [
        {"min": 1, "max": 4, "discount": 0},
        {"min": 5, "max": 9, "discount": 3},
        {"min": 10, "max": 14, "discount": 7},
        {"min": 15, "max": 19, "discount": 10},
        {"min": 20, "max": 29, "discount": 13},
        {"min": 30, "max": 49, "discount": 17},
        {"min": 50, "max": None, "discount": 18},
    ]
    return render(request, "corporate/order_request.html", {
        "course": course_obj,
        "form": form,
        "tiers": tiers,
    })


def corporate_order_portal(request, token):
    order = get_object_or_404(
        CorporateOrder.objects.select_related("organization", "course"),
        manage_token=token,
    )

    if request.method == "POST" and request.POST.get("action") == "revoke":
        invitation = get_object_or_404(
            CorporateInvitation,
            pk=request.POST.get("invitation_id"),
            order=order,
        )
        if invitation.status == CorporateInvitation.PENDING:
            invitation.status = CorporateInvitation.REVOKED
            invitation.save(update_fields=["status", "updated_at"])
            messages.success(request, "Приглашение отозвано, место снова доступно.")
        else:
            messages.error(request, "Отозвать можно только неактивированное приглашение.")
        return redirect("corporate_order_portal", token=order.manage_token)

    form = CorporateParticipantsForm(order=order)
    if request.method == "POST" and request.POST.get("action") != "revoke":
        form = CorporateParticipantsForm(request.POST, order=order)
        if order.status != CorporateOrder.PAID:
            messages.error(request, "Распределять места можно после подтверждения оплаты.")
        elif form.is_valid():
            created = []
            try:
                with transaction.atomic():
                    locked_order = CorporateOrder.objects.select_for_update().get(pk=order.pk)
                    participants = form.cleaned_data["participants"]

                    used = locked_order.invitations.exclude(
                        status=CorporateInvitation.REVOKED
                    ).count()
                    if used + len(participants) > locked_order.seats_purchased:
                        raise ValidationError(
                            f"Недостаточно свободных мест. Осталось: {locked_order.seats_purchased - used}."
                        )

                    for participant in participants:
                        invitation = CorporateInvitation.objects.filter(
                            order=locked_order,
                            email=participant["email"],
                            status=CorporateInvitation.REVOKED,
                        ).first()

                        if invitation:
                            invitation.first_name = participant["first_name"]
                            invitation.last_name = participant["last_name"]
                            invitation.status = CorporateInvitation.PENDING
                            invitation.user = None
                            invitation.activated_at = None
                            invitation.token = uuid.uuid4()
                            invitation.save()
                        else:
                            invitation = CorporateInvitation.objects.create(
                                order=locked_order,
                                **participant,
                            )
                        created.append(invitation)
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                for invitation in created:
                    _send_corporate_invitation(request, invitation)
                messages.success(
                    request,
                    f"Создано приглашений: {len(created)}. Каждому слушателю отправлена персональная ссылка."
                )
                return redirect("corporate_order_portal", token=order.manage_token)

    invitations = order.invitations.select_related("user", "enrollment").order_by("created_at")
    return render(request, "corporate/order_portal.html", {
        "order": order,
        "invitations": invitations,
        "form": form,
    })


def corporate_invitation_accept(request, token):
    invitation = get_object_or_404(
        CorporateInvitation.objects.select_related(
            "order__organization",
            "order__course",
            "user",
        ),
        token=token,
    )

    if invitation.status == CorporateInvitation.REVOKED:
        return render(request, "corporate/invitation.html", {
            "invitation": invitation,
            "revoked": True,
        })

    if not request.user.is_authenticated:
        next_url = request.path
        return render(request, "corporate/invitation.html", {
            "invitation": invitation,
            "next": next_url,
        })

    email_matches = (
        (request.user.email or "").strip().lower()
        == invitation.email.strip().lower()
    )

    if request.method == "POST" and email_matches:
        try:
            with transaction.atomic():
                locked = CorporateInvitation.objects.select_for_update().select_related(
                    "order__organization",
                    "order__course",
                ).get(pk=invitation.pk)
                enrollment = locked.activate_for(request.user)

                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                if not profile.company:
                    profile.company = locked.order.organization.name
                    profile.save(update_fields=["company", "updated_at"])
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(
                request,
                f"Корпоративный доступ активирован. Оплачивать курс повторно не нужно."
            )
            return redirect("course_learn", course_slug=enrollment.course.slug)

    return render(request, "corporate/invitation.html", {
        "invitation": invitation,
        "email_matches": email_matches,
        "already_activated": (
            invitation.status == CorporateInvitation.ACTIVATED
            and invitation.user_id == request.user.id
        ),
    })


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

        if Enrollment.objects.filter(
            user=request.user,
            course=course,
            is_deleted=False,
        ).exists():
            messages.info(request, "Доступ к этому курсу у вас уже есть.")
            return redirect("course_learn", course_slug=course.slug)

        amount = course.discount_price or course.price or 0
        if amount <= 0:
            Enrollment.objects.get_or_create(user=request.user, course=course)
            return redirect("course_learn", course_slug=course.slug)

        payment = Payment.objects.filter(
            user=request.user,
            course=course,
            status=Payment.PENDING,
            is_deleted=False,
        ).order_by("-created_at").first()

        if payment is None:
            payment = Payment.objects.create(
                user=request.user,
                course=course,
                amount=amount,
                status=Payment.PENDING,
                kaspi_invoice_id=f"QR-{uuid.uuid4().hex[:16].upper()}",
            )
        elif payment.amount != amount:
            payment.amount = amount
            payment.save(update_fields=["amount", "updated_at"])
        
        return render(request, "payment/payment_page.html", {
            "course": course,
            "amount": amount,
            "kaspi_url": getattr(settings, "KASPI_PAYMENT_URL", ""),
            "payment": payment,
            "last_payment": payment,
            "automatic_payment_enabled": bool(
                getattr(settings, "KASPI_WEBHOOK_SECRET", "")
                or getattr(settings, "KASPI_SECRET", "")
            ),
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
    if request.method != "POST":
        return redirect("checkout", slug=slug)
    return payment_claim(request, slug)


@login_required
def payment_claim(request, slug):
    try:
        course = Course.objects.filter(
            slug=slug,
            status=Course.PUBLISHED,
            is_deleted=False,
        ).only("id", "title", "slug").order_by("id").first()
        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")

        payment = Payment.objects.filter(
            user=request.user,
            course=course,
            is_deleted=False,
        ).order_by("-created_at").first()

        if not payment:
            messages.error(request, "Платёж не найден")
            return redirect("course_detail", slug=slug)

        if payment.status == Payment.SUCCESS:
            return redirect("course_learn", course_slug=course.slug)

        receipt = request.FILES.get("receipt")
        if not receipt:
            messages.info(
                request,
                "Если платёж ещё не подтвердился автоматически, приложите чек из Kaspi."
            )
            return redirect("checkout", slug=slug)

        payment.receipt = receipt
        payment.save(update_fields=["receipt", "updated_at"])
        messages.success(
            request,
            "Чек загружен. После подтверждения платежа доступ откроется автоматически."
        )
        return redirect("payment_thanks", slug=slug)

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
def payment_status(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_related("course"),
        id=payment_id,
        user=request.user,
        is_deleted=False,
    )
    has_access = Enrollment.objects.filter(
        user=request.user,
        course=payment.course,
        is_deleted=False,
    ).exists()

    return JsonResponse({
        "status": payment.status,
        "paid": payment.status == Payment.SUCCESS,
        "has_access": has_access,
        "learn_url": (
            reverse("course_learn", args=[payment.course.slug])
            if has_access else ""
        ),
    })


@csrf_exempt
def certificate_registry_callback(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    expected_token = getattr(settings, "CERTIFICATE_REGISTRY_TOKEN", "") or ""
    received_token = str(data.get("token") or "")
    if not expected_token or not hmac.compare_digest(received_token, expected_token):
        return JsonResponse({"error": "Unauthorized"}, status=403)

    request_id = str(data.get("local_request_id") or "").strip()
    if not request_id.isdigit():
        return JsonResponse({"error": "Invalid local_request_id"}, status=400)

    cert_request = CertificateRequest.objects.filter(pk=int(request_id)).first()
    if not cert_request:
        return JsonResponse({"error": "Certificate request not found"}, status=404)

    status = str(data.get("status") or "").strip().lower()
    if status == "issued":
        cert_request.status = CertificateRequest.ISSUED
        cert_request.external_number = str(data.get("certificate_number") or "").strip()
        cert_request.pdf_url = str(data.get("pdf_url") or "").strip()
        cert_request.verify_url = str(data.get("verify_url") or "").strip()
        cert_request.issued_at = timezone.now()
        cert_request.sync_error = ""
    elif status == "rejected":
        cert_request.status = CertificateRequest.REJECTED
        cert_request.sync_error = str(data.get("error") or "Заявка отклонена реестром.")
    else:
        cert_request.status = CertificateRequest.PENDING

    cert_request.save(update_fields=[
        "status",
        "external_number",
        "pdf_url",
        "verify_url",
        "issued_at",
        "sync_error",
        "updated_at",
    ])

    return JsonResponse({"ok": True, "local_request_id": request_id})

@login_required
def payment_thanks(request, slug):
    try:
        course = Course.objects.filter(slug=slug).only('id', 'title', 'slug').order_by('id').first()
        if not course:
            messages.error(request, "Курс не найден")
            return redirect("courses_list")
            
        return render(request, "payment/payment_thanks.html", {
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
        enrollments = list(
            Enrollment.objects.filter(
                user=request.user,
                is_deleted=False,
            ).select_related(
                "course",
                "course__category",
                "course__instructor",
            ).order_by("-created_at")
        )

        progress_map = {}
        for enrollment in enrollments:
            required_blocks = LessonBlock.objects.filter(
                lesson__module__course=enrollment.course,
                is_required=True,
                is_deleted=False,
            )
            required_count = required_blocks.count()
            completed_count = BlockProgress.objects.filter(
                user=request.user,
                block__in=required_blocks,
                is_completed=True,
            ).count()
            progress_map[enrollment.course_id] = (
                round((completed_count / required_count) * 100)
                if required_count else 0
            )

        return render(request, "courses/my_courses.html", {
            "enrollments": enrollments,
            "progress_map": progress_map,
        })

    except DatabaseError as e:
        logger.error(f"Database error loading my courses: {str(e)}", exc_info=True)
        messages.error(request, "Временные проблемы с базой данных")
        return render(request, "courses/my_courses.html", {
            "enrollments": [],
            "progress_map": {},
        })
    except Exception as e:
        logger.error(f"Error loading my courses: {str(e)}", exc_info=True)
        messages.error(request, "Произошла ошибка при загрузке курсов")
        return render(request, "courses/my_courses.html", {
            "enrollments": [],
            "progress_map": {},
        })

@login_required
def dashboard(request):
    try:
        user = request.user
        
        my_courses_qs = Course.objects.filter(
            enrollments__user=user,
            enrollments__is_deleted=False,
        ).distinct().only('id', 'title', 'slug', 'created_at')[:10]
        
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
def certificate_options(request, course_slug):
    course_obj = get_object_or_404(Course, slug=course_slug, is_deleted=False)
    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course_obj,
        is_deleted=False,
    )

    if not enrollment.completed or not enrollment.completed_at:
        messages.error(request, "Сертификат станет доступен после завершения курса.")
        return redirect("my_courses")

    existing_request = CertificateRequest.objects.filter(enrollment=enrollment).first()
    probe = existing_request or CertificateRequest(
        enrollment=enrollment,
        user=request.user,
        course=course_obj,
        period_mode=CertificateRequest.WITHOUT_PERIOD,
    )

    min_days = probe.minimum_training_days
    actual_days = probe.actual_training_days
    period_allowed = probe.period_is_allowed
    period_eligible_date = probe.period_eligible_date
    start_date = enrollment.enrolled_at.date()
    completion_date = enrollment.completed_at.date()
    certificate_period_end = probe.certificate_period_end

    if request.method == "POST":
        mode = request.POST.get("period_mode", CertificateRequest.WITHOUT_PERIOD)
        if mode not in {CertificateRequest.WITH_PERIOD, CertificateRequest.WITHOUT_PERIOD}:
            mode = CertificateRequest.WITHOUT_PERIOD

        if mode == CertificateRequest.WITH_PERIOD and not period_allowed:
            messages.error(
                request,
                f"Период обучения пока нельзя указать: для курса объёмом {course_obj.duration_hours or 0} "
                f"академических часов требуется не менее {min_days} календарных дней с даты регистрации. "
                f"Сертификат с периодом будет доступен {period_eligible_date:%d.%m.%Y}. "
                f"Сейчас можно выбрать сертификат без периода."
            )
        else:
            cert_request, _ = CertificateRequest.objects.update_or_create(
                enrollment=enrollment,
                defaults={
                    "user": request.user,
                    "course": course_obj,
                    "period_mode": mode,
                    "status": CertificateRequest.PENDING,
                },
            )
            cert_request.save()
            try:
                sync_certificate_request(cert_request)
                messages.success(
                    request,
                    "Заявка на сертификат автоматически передана в реестр SkillsSpire. "
                    "Повторно вводить ФИО, курс, часы и даты не требуется."
                )
            except CertificateRegistryError as exc:
                cert_request.sync_error = str(exc)
                cert_request.save(update_fields=["sync_error", "updated_at"])
                logger.warning(
                    "Certificate registry sync failed for request %s: %s",
                    cert_request.pk,
                    exc,
                )
                messages.info(
                    request,
                    "Выбор сертификата сохранён. Автоматическая передача в реестр пока не настроена; "
                    "заявка не потеряна и может быть отправлена после подключения реестра."
                )
            return redirect("certificate_options", course_slug=course_slug)

    return render(request, "certificates/options.html", {
        "course": course_obj,
        "enrollment": enrollment,
        "certificate_request": existing_request,
        "min_days": min_days,
        "actual_days": actual_days,
        "period_allowed": period_allowed,
        "period_eligible_date": period_eligible_date,
        "certificate_period_end": certificate_period_end,
        "start_date": start_date,
        "completion_date": completion_date,
    })

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