from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.contrib.auth import login
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.conf import settings
import hmac, hashlib, json

from .forms import CustomUserCreationForm, ReviewForm, ContactForm
from .models import Course, Category, Lesson, Enrollment, Review, Wishlist, Payment, InstructorProfile, User

# ------------------------ Kaspi Webhook ------------------------
@csrf_exempt
def kaspi_webhook(request):
    if request.method != "POST":
        return JsonResponse({'error': 'Invalid method'}, status=400)

    signature = request.headers.get('X-Kaspi-Signature')
    body = request.body

    # Проверка подписи
    expected_signature = hmac.new(
        key=settings.KASPI_SECRET.encode(),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()

    if signature != expected_signature:
        return JsonResponse({'error': 'Invalid signature'}, status=403)

    try:
        data = json.loads(body)
        invoice_id = data.get('invoiceId')
        status = data.get('status')
        payment = Payment.objects.get(kaspi_invoice_id=invoice_id)
    except (Payment.DoesNotExist, json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Payment not found or invalid data'}, status=404)

    payment.status = status
    payment.save()

    if status == 'success':
        Enrollment.objects.get_or_create(user=payment.user, course=payment.course)
        payment.course.students.add(payment.user)

    return JsonResponse({'status': 'ok'})

# ------------------------ User Signup ------------------------
def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать!')
            return redirect('home')
        messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

# ------------------------ Home Page ------------------------
# --- home() ---
def home(request):
    featured_courses = Course.objects.filter(is_featured=True).select_related('category')[:6]
    popular_courses = (
        Course.objects
        .annotate(num_students=Count('students', distinct=True))
        .select_related('category')
        .order_by('-num_students')[:6]
    )
    categories = Category.objects.filter(is_active=True)[:8]

    context = {
        'featured_courses': featured_courses,
        'popular_courses': popular_courses,
        'categories': categories,
    }
    return render(request, 'home.html', context)

# ------------------------ Courses List ------------------------
def courses_list(request):
    courses = Course.objects.select_related('category').prefetch_related('students', 'reviews').all()

    category_slug = request.GET.get('category')
    search_query = request.GET.get('q', '')
    level = request.GET.get('level')
    price_filter = request.GET.get('price')
    sort_by = request.GET.get('sort', 'newest')

    if category_slug:
        courses = courses.filter(category__slug=category_slug)
    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )
    if level:
        courses = courses.filter(level=level)
    if price_filter == 'free':
        courses = courses.filter(price=0)
    elif price_filter == 'paid':
        courses = courses.filter(price__gt=0)

    if sort_by == 'popular':
        courses = courses.annotate(students_count=Count('students')).order_by('-students_count')
    elif sort_by == 'rating':
        courses = courses.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
    elif sort_by == 'price_low':
        courses = courses.order_by('price')
    elif sort_by == 'price_high':
        courses = courses.order_by('-price')
    else:
        courses = courses.order_by('-created_at')

    categories = Category.objects.filter(is_active=True)
    paginator = Paginator(courses, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'courses/list.html', {
        'courses': page_obj,
        'categories': categories,
        'is_paginated': True,
        'page_obj': page_obj,
    })

# ------------------------ Course Detail ------------------------
def course_detail(request, slug):
    course = get_object_or_404(Course.objects.select_related('category').prefetch_related('students', 'reviews'), slug=slug)
    if not request.user.is_authenticated and not course.is_free:
        messages.info(request, 'Для доступа к курсу необходимо авторизоваться')
        return redirect('login')

    has_access = request.user.is_authenticated and (course.students.filter(id=request.user.id).exists() or course.is_free)

    lessons = Lesson.objects.filter(module__course=course, is_active=True).select_related('module').order_by('module__order', 'order')
    related_courses = Course.objects.filter(category=course.category).exclude(id=course.id).select_related('category')[:4]
    reviews = Review.objects.filter(course=course, is_active=True).select_related('user')[:10]

    context = {
        'course': course,
        'lessons': lessons,
        'related_courses': related_courses,
        'reviews': reviews,
        'has_access': has_access,
    }
    return render(request, 'courses/detail.html', context)

# ------------------------ Lesson Detail ------------------------
@login_required
def lesson_detail(request, course_slug, lesson_slug):
    course = get_object_or_404(Course.objects.prefetch_related('students'), slug=course_slug)
    lesson = get_object_or_404(Lesson.objects.select_related('module'), slug=lesson_slug, module__course=course, is_active=True)

    if not course.students.filter(id=request.user.id).exists() and not course.is_free:
        messages.error(request, 'У вас нет доступа к этому уроку')
        return redirect('course_detail', slug=course_slug)

    lessons_list = Lesson.objects.filter(module__course=course, is_active=True).order_by('module__order', 'order')
    lessons_list = list(lessons_list)
    current_index = lessons_list.index(lesson)
    previous_lesson = lessons_list[current_index - 1] if current_index > 0 else None
    next_lesson = lessons_list[current_index + 1] if current_index < len(lessons_list) - 1 else None

    # LessonProgress.objects.update_or_create(
    #     user=request.user,
    #     lesson=lesson,
    #     defaults={'last_accessed': timezone.now()}
    # )

    return render(request, 'courses/lesson_detail.html', {
        'course': course,
        'lesson': lesson,
        'previous_lesson': previous_lesson,
        'next_lesson': next_lesson,
    })

# ------------------------ Enroll Course ------------------------
@login_required
def enroll_course(request, slug):
    course = get_object_or_404(Course.objects.prefetch_related('students'), slug=slug)

    if course.students.filter(id=request.user.id).exists():
        messages.info(request, 'Вы уже записаны на этот курс')
        return redirect('course_detail', slug=slug)

    if course.price > 0:
        messages.error(request, 'Для записи на платный курс необходимо произвести оплату')
        return redirect('payment:create', course_slug=slug)

    Enrollment.objects.get_or_create(user=request.user, course=course)
    course.students.add(request.user)

    messages.success(request, f'Вы успешно записаны на курс "{course.title}"')
    return redirect('course_detail', slug=slug)

# ------------------------ My Courses ------------------------
@login_required
def my_courses(request):
    enrollments = Enrollment.objects.filter(user=request.user).select_related('course')
    in_progress = enrollments.filter(completed=False)
    completed = enrollments.filter(completed=True)

    return render(request, 'courses/my_courses.html', {
        'in_progress': in_progress,
        'completed': completed,
    })

# ------------------------ Dashboard ------------------------
@login_required
def dashboard(request):
    user = request.user
    enrollments = Enrollment.objects.filter(user=user).select_related('course')
    progress = LessonProgress.objects.filter(user=user).select_related('lesson')

    context = {
        'total_courses': enrollments.count(),
        'completed_courses': enrollments.filter(completed=True).count(),
        'total_lessons': progress.count(),
        'completed_lessons': progress.filter(completed=True).count(),
        'recent_courses': enrollments.order_by('-enrolled_at')[:5],
    }
    return render(request, 'users/dashboard.html', context)

# ------------------------ Add Review ------------------------
@login_required
def add_review(request, slug):
    course = get_object_or_404(Course.objects.prefetch_related('students'), slug=slug)

    if not course.students.filter(id=request.user.id).exists():
        messages.error(request, 'Только студенты курса могут оставлять отзывы')
        return redirect('course_detail', slug=slug)
    if Review.objects.filter(course=course, user=request.user).exists():
        messages.error(request, 'Вы уже оставили отзыв на этот курс')
        return redirect('course_detail', slug=slug)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.course = course
            review.user = request.user
            review.save()
            messages.success(request, 'Ваш отзыв успешно добавлен')
            return redirect('course_detail', slug=slug)
    else:
        form = ReviewForm()

    return render(request, 'courses/add_review.html', {'course': course, 'form': form})

# ------------------------ Toggle Wishlist ------------------------
@login_required
def toggle_wishlist(request, slug):
    course = get_object_or_404(Course, slug=slug)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, course=course)

    if not created:
        wishlist_item.delete()
        message = 'Курс удален из избранного'
        is_wishlisted = False
    else:
        message = 'Курс добавлен в избранное'
        is_wishlisted = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': message, 'is_wishlisted': is_wishlisted})

    messages.success(request, message)
    return redirect('course_detail', slug=slug)

# ------------------------ About ------------------------
def about(request):
    instructors = InstructorProfile.objects.filter(is_approved=True)
    stats = {
        'total_courses': Course.objects.count(),
        'total_students': User.objects.filter(enrolled_courses__isnull=False).distinct().count(),
        'total_instructors': instructors.count(),
    }
    return render(request, 'about.html', {'instructors': instructors, 'stats': stats})

# ------------------------ Contact ------------------------
def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ваше сообщение успешно отправлено!')
            return redirect('contact')
    else:
        form = ContactForm()
    return render(request, 'contact.html', {'form': form})

# ------------------------ Design Wireframe ------------------------
def design_wireframe(request):
    features = [
        {'title': 'Практика', 'description': 'Проекты в портфолио'},
        {'title': 'Наставник', 'description': 'Обратная связь'},
        {'title': 'Гибкий формат', 'description': 'Онлайн и записи'},
        {'title': 'Комьюнити', 'description': 'Чаты и ревью'},
        {'title': 'Карьерный трек', 'description': 'Помощь с резюме'},
        {'title': 'Сертификат', 'description': 'После защиты'},
    ]
    return render(request, 'design_wireframe.html', {'features': features})
