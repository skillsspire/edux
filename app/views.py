from django.core.exceptions import FieldDoesNotExist
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import DatabaseError, ProgrammingError
from django.db.models import Q, Avg, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

import hmac
import hashlib
import json
import os
from typing import Optional

from supabase import create_client, Client

from .forms import ContactForm, CustomUserCreationForm, ReviewForm
from .models import (
    Category,
    Course,
    Enrollment,
    InstructorProfile,
    Lesson,
    LessonProgress,
    Payment,
    Review,
    Wishlist,
    Article,
    Material,
)


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

def _get_course_image_data(course):
    """Возвращает данные курса с изображением в виде словаря"""
    thumb_name = getattr(getattr(course, "thumbnail", None), "name", None)
    image_name = getattr(getattr(course, "image", None), "name", None)
    image_url = public_storage_url(first_nonempty(thumb_name, image_name))
    
    if not image_url:
        image_url = f"{settings.STATIC_URL}img/courses/course-placeholder.jpg"
    
    return {
        "course": course,
        "image_url": image_url,
        "title": course.title,
        "slug": course.slug,
        "category": course.category,
        "price": course.price,
        "short_description": getattr(course, "short_description", ""),
        "average_rating": getattr(course, "average_rating", "4.8"),
        "reviews_count": getattr(course, "reviews_count", 0),
        "is_popular": getattr(course, "is_popular", False),
        "has_certificate": getattr(course, "has_certificate", False),
    }

def _get_article_image_data(article):
    """Возвращает данные статьи с изображением в виде словаря"""
    if hasattr(article, "image") and article.image:
        image_url = article.image.url
    else:
        image_url = f"{settings.STATIC_URL}img/articles/article-placeholder.jpg"
    
    return {
        "article": article,
        "image_url": image_url,
        "title": article.title,
        "slug": article.slug,
        "excerpt": getattr(article, "excerpt", ""),
        "created_at": getattr(article, "created_at", None),
    }

def _get_material_image_data(material):
    """Возвращает данные материала с изображением в виде словаря"""
    if hasattr(material, "image") and material.image:
        image_url = material.image.url
    else:
        image_url = f"{settings.STATIC_URL}img/materials/material-placeholder.jpg"
    
    return {
        "material": material,
        "image_url": image_url,
        "title": material.title,
        "slug": material.slug,
        "description": getattr(material, "description", ""),
    }


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

def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
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
        messages.error(request, "Пожалуйста, исправьте ошибки в форме.")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


def home(request):
    # --- Курсы и категории ---
    featured_courses_qs = Course.objects.filter(is_featured=True).select_related("category")[:6]
    popular_courses_qs = (
        Course.objects.select_related("category")
        .prefetch_related("reviews")
        .annotate(num_students=Count("students", distinct=True))
        .order_by("-num_students")[:6]
    )
    
    # Преобразуем в словари с изображениями
    featured_courses = [_get_course_image_data(course) for course in featured_courses_qs]
    popular_courses = [_get_course_image_data(course) for course in popular_courses_qs]

    try:
        categories = Category.objects.filter(is_active=True)[:8]
    except Exception:
        categories = Category.objects.all()[:8]

    # --- Отзывы (гибрид) ---
    reviews = []
    try:
        reviews = (
            Review.objects.filter(is_active=True)
            .select_related("user", "course")
            .order_by("-created_at")[:10]
        )
        if not reviews.exists():
            raise ValueError("No local reviews")
    except Exception:
        try:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            if url and key:
                supabase: Client = create_client(url, key)
                data = supabase.table("reviews").select("*").order("created_at", desc=True).limit(10).execute()
                reviews = data.data or []
        except Exception as e:
            print("⚠️ Ошибка загрузки отзывов:", e)
            reviews = []

    # --- Статьи ---
    latest_articles_qs = Article.objects.all()
    if _has_field(Article, "status"):
        latest_articles_qs = latest_articles_qs.filter(status="published")
    if _has_field(Article, "published_at"):
        latest_articles_qs = latest_articles_qs.order_by("-published_at")
    elif _has_field(Article, "created_at"):
        latest_articles_qs = latest_articles_qs.order_by("-created_at")
    latest_articles_qs = latest_articles_qs[:3]
    
    latest_articles = [_get_article_image_data(article) for article in latest_articles_qs]

    # --- Материалы ---
    latest_materials_qs = Material.objects.all()
    if _has_field(Material, "is_public"):
        latest_materials_qs = latest_materials_qs.filter(is_public=True)
    if _has_field(Material, "created_at"):
        latest_materials_qs = latest_materials_qs.order_by("-created_at")
    latest_materials_qs = latest_materials_qs[:3]
    
    latest_materials = [_get_material_image_data(material) for material in latest_materials_qs]

    # --- FAQ ---
    faqs = [
        {"question": "Как проходит обучение?", "answer": "Онлайн в личном кабинете: видео, задания и обратная связь."},
        {"question": "Будет ли доступ к материалам после окончания?", "answer": "Да, бессрочный доступ ко всем урокам курса."},
        {"question": "Как оплатить курс?", "answer": "Через Kaspi QR. После оплаты запись активируется автоматически."},
        {"question": "Выдаётся ли сертификат?", "answer": "Да, после завершения всех модулей."},
    ]

    return render(request, "home.html", {
        "featured_courses": featured_courses,
        "popular_courses": popular_courses,
        "categories": categories,
        "reviews": reviews,
        "latest_articles": latest_articles,
        "latest_materials": latest_materials,
        "faqs": faqs,
    })


# ---------- catalog ----------

def courses_list(request):
    courses_qs = (
        Course.objects.select_related("category")
        .prefetch_related("students", "reviews")
        .annotate(avg_rating=Avg("reviews__rating"))
    )

    search_query = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "newest")
    price_filter = request.GET.get("price")
    category_filter = request.GET.get("category")

    if search_query:
        courses_qs = courses_qs.filter(
            Q(title__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )

    if category_filter:
        courses_qs = courses_qs.filter(category__slug=category_filter)

    if price_filter == "free":
        courses_qs = courses_qs.filter(price=0)
    elif price_filter == "paid":
        courses_qs = courses_qs.filter(price__gt=0)

    if sort_by == "popular":
        courses_qs = courses_qs.annotate(
            students_count=Count("students", distinct=True)
        ).order_by("-students_count", "-created_at")
    elif sort_by == "rating":
        courses_qs = courses_qs.order_by("-avg_rating", "-created_at")
    elif sort_by == "price_low":
        courses_qs = courses_qs.order_by("price", "-created_at")
    elif sort_by == "price_high":
        courses_qs = courses_qs.order_by("-price", "-created_at")
    else:
        courses_qs = courses_qs.order_by("-created_at")

    paginator = Paginator(courses_qs, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Преобразуем в словари с изображениями
    courses_with_images = [_get_course_image_data(course) for course in page_obj]

    try:
        categories = Category.objects.filter(is_active=True)
    except Exception:
        categories = Category.objects.all()

    return render(request, "courses/list.html", {
        "courses": courses_with_images,
        "categories": categories,
        "is_paginated": page_obj.has_other_pages(),
        "page_obj": page_obj,
        "q": search_query,
        "sort_by": sort_by,
    })


def articles_list(request):
    qs = Article.objects.all()
    # безопасный фильтр по статусу
    if _has_field(Article, "status"):
        qs = qs.filter(status="published")
    # безопасная сортировка
    if _has_field(Article, "published_at"):
        qs = qs.order_by("-published_at")
    elif _has_field(Article, "created_at"):
        qs = qs.order_by("-created_at")
    else:
        qs = qs.order_by("-id")
    
    # Преобразуем в словари с изображениями
    articles = [_get_article_image_data(article) for article in qs[:50]]
        
    return render(request, "articles/list.html", {"articles": articles})


def article_detail(request, slug):
    # собираем фильтр безопасно
    flt = {"slug": slug}
    if _has_field(Article, "status"):
        flt["status"] = "published"

    article_obj = get_object_or_404(Article, **flt)
    article = _get_article_image_data(article_obj)

    latest_qs = Article.objects.exclude(pk=article_obj.pk)
    if _has_field(Article, "status"):
        latest_qs = latest_qs.filter(status="published")
    if _has_field(Article, "published_at"):
        latest_qs = latest_qs.order_by("-published_at")
    elif _has_field(Article, "created_at"):
        latest_qs = latest_qs.order_by("-created_at")
    else:
        latest_qs = latest_qs.order_by("-id")

    # Преобразуем в словари с изображениями
    latest_articles = [_get_article_image_data(article) for article in latest_qs[:4]]

    return render(request, "articles/detail.html", {
        "article": article, 
        "latest": latest_articles
    })


def materials_list(request):
    qs = Material.objects.all()
    if _has_field(Material, "is_public"):
        qs = qs.filter(is_public=True)
    if _has_field(Material, "created_at"):
        qs = qs.order_by("-created_at")
    else:
        qs = qs.order_by("-id")
    
    # Преобразуем в словари с изображениями
    materials = [_get_material_image_data(material) for material in qs[:50]]
        
    return render(request, "materials/list.html", {"materials": materials})


# ---------- course detail & lessons ----------

def course_detail(request, slug):
    course_obj = get_object_or_404(
        Course.objects.select_related("category", "instructor").prefetch_related("students", "reviews"),
        slug=slug
    )
    
    course_data = _get_course_image_data(course_obj)

    # доступ
    has_access = True
    if course_obj.price and float(course_obj.price or 0) > 0:
        has_access = request.user.is_authenticated and course_obj.students.filter(id=request.user.id).exists()

    # уроки
    try:
        lessons = (
            Lesson.objects.filter(module__course=course_obj, is_active=True)
            .select_related("module")
            .order_by("module__order", "order")
        )
    except (ProgrammingError, DatabaseError):
        lessons = Lesson.objects.none()

    # похожие курсы
    related_courses_qs = (
        Course.objects.filter(category=course_obj.category)
        .exclude(id=course_obj.id).select_related("category")[:4]
    )
    
    # Преобразуем в словари с изображениями
    related_courses = [_get_course_image_data(course) for course in related_courses_qs]

    # отзывы
    reviews = Review.objects.filter(course=course_obj, is_active=True).select_related("user")[:10]

    # преподаватель
    teacher_user = getattr(course_obj, "instructor", None)
    teacher_profile = getattr(teacher_user, "instructor_profile", None)

    # избранное
    is_in_wishlist = False
    if request.user.is_authenticated:
        is_in_wishlist = Wishlist.objects.filter(user=request.user, course=course_obj).exists()

    return render(request, "courses/detail.html", {
        "course": course_data,
        "course_obj": course_obj,  # сохраняем оригинальный объект для совместимости
        "lessons": lessons,
        "related_courses": related_courses,
        "reviews": reviews,
        "has_access": has_access,
        "teacher": teacher_user,
        "teacher_profile": teacher_profile,
        "is_in_wishlist": is_in_wishlist,
    })


@login_required
def lesson_detail(request, course_slug, lesson_slug):
    course_obj = get_object_or_404(Course.objects.prefetch_related("students"), slug=course_slug)
    course_data = _get_course_image_data(course_obj)

    try:
        lesson = get_object_or_404(
            Lesson.objects.select_related("module"),
            slug=lesson_slug, module__course=course_obj, is_active=True
        )
    except (ProgrammingError, DatabaseError):
        messages.error(request, "Секции модулей пока недоступны. Попробуйте позже.")
        return redirect("course_detail", slug=course_slug)

    if course_obj.price and float(course_obj.price or 0) > 0 and not course_obj.students.filter(id=request.user.id).exists():
        messages.error(request, "У вас нет доступа к этому уроку")
        return redirect("course_detail", slug=course_slug)

    # соседние уроки
    try:
        lessons_list = list(
            Lesson.objects.filter(module__course=course_obj, is_active=True)
            .order_by("module__order", "order")
        )
    except (ProgrammingError, DatabaseError):
        lessons_list = [lesson]

    try:
        current_index = lessons_list.index(lesson)
    except ValueError:
        current_index = 0

    previous_lesson = lessons_list[current_index - 1] if current_index > 0 else None
    next_lesson = lessons_list[current_index + 1] if current_index < len(lessons_list) - 1 else None

    LessonProgress.objects.update_or_create(
        user=request.user,
        lesson=lesson,
        defaults={
            "is_completed": False if (course_obj.price and float(course_obj.price or 0) > 0) else True,
            "percent": 0,
            "updated_at": timezone.now(),
        }
    )

    enrollment = Enrollment.objects.filter(user=request.user, course=course_obj).first()

    return render(request, "courses/lesson_detail.html", {
        "course": course_data,
        "course_obj": course_obj,
        "lesson": lesson,
        "prev_lesson": previous_lesson,
        "next_lesson": next_lesson,
        "enrollment": enrollment,
    })


# ---------- enrollment & payments ----------

@login_required
def enroll_course(request, slug):
    course = get_object_or_404(Course.objects.prefetch_related("students"), slug=slug)

    if course.students.filter(id=request.user.id).exists():
        messages.info(request, "Вы уже записаны на этот курс")
        return redirect("course_detail", slug=slug)

    if course.price and float(course.price or 0) > 0:
        return redirect("create_payment", slug=slug)

    Enrollment.objects.get_or_create(user=request.user, course=course)
    course.students.add(request.user)
    messages.success(request, f'Вы успешно записаны на курс "{course.title}"')
    return redirect("course_detail", slug=slug)


@login_required
def create_payment(request, slug):
    course = get_object_or_404(Course, slug=slug)
    amount = course.discount_price or course.price or 0
    payment = Payment.objects.create(
        user=request.user,
        course=course,
        amount=amount,
        status="pending",
        kaspi_invoice_id=f"QR{timezone.now().timestamp()}",
    )
    return render(request, "payments/payment_page.html", {
        "course": course,
        "amount": amount,
        "kaspi_url": getattr(settings, "KASPI_PAYMENT_URL", ""),
        "payment": payment,
    })


@login_required
def payment_claim(request, slug):
    course = get_object_or_404(Course, slug=slug)
    payment = Payment.objects.filter(user=request.user, course=course).order_by("-id").first()
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

    return render(request, "payments/payment_claim.html", {"course": course, "payment": payment})


@login_required
def payment_thanks(request, slug):
    course = get_object_or_404(Course, slug=slug)
    return render(request, "payments/payment_thanks.html", {"course": course})


# ---------- user area ----------

@login_required
def my_courses(request):
    enrollments = Enrollment.objects.filter(user=request.user).select_related("course")
    
    # Преобразуем в словари с изображениями
    courses_with_images = []
    for enrollment in enrollments:
        course_data = _get_course_image_data(enrollment.course)
        course_data["enrollment"] = enrollment
        courses_with_images.append(course_data)
        
    in_progress = [c for c in courses_with_images if not c["enrollment"].completed]
    completed = [c for c in courses_with_images if c["enrollment"].completed]
    
    return render(request, "courses/my_courses.html", {
        "in_progress": in_progress,
        "completed": completed,
    })


@login_required
def dashboard(request):
    user = request.user

    my_courses_qs = Course.objects.filter(students__id=user.id).select_related("category")
    
    # Преобразуем в словари с изображениями
    my_courses = [_get_course_image_data(course) for course in my_courses_qs]
        
    total_courses = len(my_courses)
    recent_courses = sorted(my_courses, key=lambda x: x["course"].created_at, reverse=True)[:5]

    # completed courses
    try:
        completed_courses = Enrollment.objects.filter(user_id=user.id, completed=True).count()
    except Exception:
        try:
            completed_courses = Enrollment.objects.filter(student_id=user.id, completed=True).count()
        except Exception:
            completed_courses = 0

    # lessons progress
    try:
        progress_qs = LessonProgress.objects.filter(user=user).select_related("lesson")
        total_lessons = progress_qs.count()
        completed_lessons = progress_qs.filter(is_completed=True).count()
    except Exception:
        total_lessons = 0
        completed_lessons = 0

    context = {
        "total_courses": total_courses,
        "completed_courses": completed_courses,
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "recent_courses": recent_courses,
    }
    return render(request, "users/dashboard.html", context)


# ---------- reviews & wishlist ----------

@login_required
def add_review(request, slug):
    course = get_object_or_404(Course.objects.prefetch_related("students"), slug=slug)

    if not course.students.filter(id=request.user.id).exists():
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

    return render(request, "courses/add_review.html", {"course": course, "form": form})


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

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": message, "in_wishlist": in_wishlist})

    messages.success(request, message)
    return redirect("course_detail", slug=slug)


# ---------- static pages ----------

def about(request):
    try:
        instructors = InstructorProfile.objects.filter(is_approved=True)
        total_instructors = instructors.count()
    except Exception:
        instructors, total_instructors = [], 0

    try:
        stats = {
            "total_courses": Course.objects.count(),
            "total_students": User.objects.filter(enrolled_courses__isnull=False).distinct().count(),
            "total_instructors": total_instructors,
        }
    except Exception:
        stats = {"total_courses": 0, "total_students": 0, "total_instructors": total_instructors}

    return render(request, "about.html", {"instructors": instructors, "stats": stats})


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Ваше сообщение успешно отправлено!")
            return redirect("contact")
    else:
        form = ContactForm()
    return render(request, "contact.html", {"form": form})


def design_wireframe(request):
    features = [
        {"title": "Практика", "description": "Проекты в портфолио"},
        {"title": "Наставник", "description": "Обратная связь"},
        {"title": "Гибкий формат", "description": "Онлайн и записи"},
        {"title": "Комьюнити", "description": "Чаты и ревью"},
        {"title": "Карьерный трек", "description": "Помощь с резюме"},
        {"title": "Сертификат", "description": "После защиты"},
    ]
    return render(request, "design_wireframe.html", {"features": features})