import hmac
import hashlib
import json
import os

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
)

from typing import Optional, List, Dict, Any


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
    if amount and float(amount) < float(payment.amount):
        return JsonResponse({"error": "Invalid amount"}, status=400)
    payment.status = status
    payment.save()
    if status == "success":
        Enrollment.objects.get_or_create(user=payment.user, course=payment.course)
        payment.course.students.add(payment.user)
    return JsonResponse({"status": "ok"})


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
    featured_courses = Course.objects.filter(is_featured=True).select_related("category")[:6]
    popular_courses = (
        Course.objects.select_related("category")
        .prefetch_related("reviews")
        .annotate(num_students=Count("students", distinct=True))
        .order_by("-num_students")[:6]
    )
    try:
        categories = Category.objects.filter(is_active=True)[:8]
    except Exception:
        categories = Category.objects.all()[:8]
    reviews = (
        Review.objects.filter(is_active=True)
        .select_related("user", "course")
        .order_by("-created_at")[:10]
    )
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
        "faqs": faqs,
    })


def courses_list(request):
    courses_qs = (
        Course.objects.select_related("category")
        .prefetch_related("students", "reviews")
        .annotate(avg_rating=Avg("reviews__rating"))
    )
    selected_categories = request.GET.getlist("category")
    selected_levels = request.GET.getlist("level")
    search_query = request.GET.get("q", "").strip()
    price_filter = request.GET.get("price")
    sort_by = request.GET.get("sort", "newest")
    if selected_categories:
        courses_qs = courses_qs.filter(category__slug__in=selected_categories)
    if search_query:
        courses_qs = courses_qs.filter(
            Q(title__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )
    if selected_levels:
        courses_qs = courses_qs.filter(level__in=selected_levels)
    if price_filter == "free":
        courses_qs = courses_qs.filter(price=0)
    elif price_filter == "paid":
        courses_qs = courses_qs.filter(price__gt=0)
    if sort_by == "popular":
        courses_qs = courses_qs.annotate(students_count=Count("students", distinct=True)).order_by("-students_count", "-created_at")
    elif sort_by == "rating":
        courses_qs = courses_qs.order_by("-avg_rating", "-created_at")
    elif sort_by == "price_low":
        courses_qs = courses_qs.order_by("price", "-created_at")
    elif sort_by == "price_high":
        courses_qs = courses_qs.order_by("-price", "-created_at")
    else:
        courses_qs = courses_qs.order_by("-created_at")
    try:
        categories = Category.objects.filter(is_active=True)
    except Exception:
        categories = Category.objects.all()
    paginator = Paginator(courses_qs, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "courses/list.html", {
        "courses": page_obj,
        "categories": categories,
        "is_paginated": page_obj.has_other_pages(),
        "page_obj": page_obj,
        "q": search_query,
        "selected_levels": selected_levels,
        "selected_categories": selected_categories,
        "price_filter": price_filter,
        "sort_by": sort_by,
    })


def course_detail(request, slug):
    course = get_object_or_404(
        Course.objects.select_related("category", "instructor").prefetch_related("students", "reviews"),
        slug=slug
    )
    has_access = True
    if course.price and float(course.price) > 0:
        has_access = request.user.is_authenticated and course.students.filter(id=request.user.id).exists()
    try:
        lessons = (
            Lesson.objects.filter(module__course=course, is_active=True)
            .select_related("module")
            .order_by("module__order", "order")
        )
    except (ProgrammingError, DatabaseError):
        lessons = Lesson.objects.none()
    
    related_courses = (
        Course.objects.filter(category=course.category)
        .exclude(id=course.id).select_related("category")[:4]
    )
    
    related_courses_with_images = []
    for related_course in related_courses:
        related_courses_with_images.append({
            'course': related_course,
            'image_url': related_course.display_image_url
        })
    
    reviews = Review.objects.filter(course=course, is_active=True).select_related("user")[:10]
    instructor_profile = None
    if course.instructor_id:
        instructor_profile = getattr(course.instructor, "instructor_profile", None)
    teacher = instructor_profile
    
    return render(request, "courses/detail.html", {
        "course": course,
        "lessons": lessons,
        "related_courses_with_images": related_courses_with_images,
        "reviews": reviews,
        "has_access": has_access,
        "teacher": teacher,
        "course_image_url": course.display_image_url,
    })


@login_required
def lesson_detail(request, course_slug, lesson_slug):
    course = get_object_or_404(Course.objects.prefetch_related("students"), slug=course_slug)
    try:
        lesson = get_object_or_404(
            Lesson.objects.select_related("module"),
            slug=lesson_slug, module__course=course, is_active=True
        )
    except (ProgrammingError, DatabaseError):
        messages.error(request, "Секции модулей пока недоступны. Попробуйте позже.")
        return redirect("course_detail", slug=course_slug)
    if course.price and float(course.price) > 0 and not course.students.filter(id=request.user.id).exists():
        messages.error(request, "У вас нет доступа к этому уроку")
        return redirect("course_detail", slug=course_slug)
    try:
        lessons_list = list(
            Lesson.objects.filter(module__course=course, is_active=True)
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
            "is_completed": False if (course.price and float(course.price) > 0) else True,
            "percent": 0,
            "updated_at": timezone.now(),
        }
    )
    enrollment = None
    try:
        enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
    except Exception:
        enrollment = None
    return render(request, "courses/lesson_detail.html", {
        "course": course,
        "lesson": lesson,
        "prev_lesson": previous_lesson,
        "next_lesson": next_lesson,
        "enrollment": enrollment,
    })


@login_required
def enroll_course(request, slug):
    course = get_object_or_404(Course.objects.prefetch_related("students"), slug=slug)
    if course.students.filter(id=request.user.id).exists():
        messages.info(request, "Вы уже записаны на этот курс")
        return redirect("course_detail", slug=slug)
    if course.price and float(course.price) > 0:
        return redirect("create_payment", slug=slug)
    Enrollment.objects.get_or_create(user=request.user, course=course)
    course.students.add(request.user)
    messages.success(request, f'Вы успешно записаны на курс "{course.title}"')
    return redirect("course_detail", slug=slug)


@login_required
def create_payment(request, slug):
    course = get_object_or_404(Course, slug=slug)
    amount = course.discount_price or course.price
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
        "kaspi_url": settings.KASPI_PAYMENT_URL,
        "payment": payment,
    })


@login_required
def payment_claim(request, slug):
    course = get_object_or_404(Course, slug=slug)
    payment = Payment.objects.filter(user=request.user, course=course).order_by("-created").first()
    if not payment:
        messages.error(request, "Платеж не найден")
        return redirect("course_detail", slug=slug)
    if request.method == "POST" and request.FILES.get("receipt"):
        if hasattr(payment, "receipt"):
            payment.receipt = request.FILES["receipt"]
        payment.save()
        messages.success(request, "Чек успешно загружен, ожидайте подтверждения")
        return redirect("payment_thanks", slug=slug)
    return render(request, "payments/payment_claim.html", {"course": course, "payment": payment})


@login_required
def payment_thanks(request, slug):
    course = get_object_or_404(Course, slug=slug)
    return render(request, "payments/payment_thanks.html", {"course": course})


@login_required
def my_courses(request):
    enrollments = Enrollment.objects.filter(user=request.user).select_related("course")
    in_progress = enrollments.filter(completed=False)
    completed = enrollments.filter(completed=True)
    return render(request, "courses/my_courses.html", {
        "in_progress": in_progress,
        "completed": completed,
    })


@login_required
def dashboard(request):
    user = request.user
    my_courses = Course.objects.filter(students__id=user.id).select_related("category")
    total_courses = my_courses.count()
    recent_courses = my_courses.order_by("-created_at")[:5]
    try:
        completed_courses = Enrollment.objects.filter(user_id=user.id, completed=True).count()
    except Exception:
        try:
            completed_courses = Enrollment.objects.filter(student_id=user.id, completed=True).count()
        except Exception:
            completed_courses = 0
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
        "enrollments": None,
    }
    return render(request, "users/dashboard.html", context)


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
    if not created:
        wishlist_item.delete()
        message = "Курс удален из избранного"
        is_wishlisted = False
    else:
        message = "Курс добавлен в избранное"
        is_wishlisted = True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": message, "is_wishlisted": is_wishlisted})
    messages.success(request, message)
    return redirect("course_detail", slug=slug)


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