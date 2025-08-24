from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.contrib.auth import login, authenticate
from .models import Course, Category, Lesson, Enrollment
from .forms import SignUpForm, EmailAuthenticationForm


def custom_login(request):
    if request.method == 'POST':
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
    else:
        form = EmailAuthenticationForm()

    return render(request, 'registration/login.html', {'form': form})


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()

    return render(request, 'registration/signup.html', {'form': form})


def contact(request):
    return render(request, 'contact.html')


def about(request):
    return render(request, 'about.html')


def home(request):
    popular_courses = Course.objects.annotate(
        num_students=Count('enrollments')
    ).order_by('-num_students')[:5]
    categories = Category.objects.all()
    return render(request, 'home.html', {
        'popular_courses': popular_courses,
        'categories': categories,
    })


def courses_list(request):
    courses = Course.objects.all().select_related("category", "author")
    categories = Category.objects.all()
    query = request.GET.get('q')
    if query:
        courses = courses.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )
    category_slug = request.GET.get('category')
    if category_slug:
        courses = courses.filter(category__slug=category_slug)
    level = request.GET.get("level")
    if level:
        courses = courses.filter(level=level)
    price = request.GET.get("price")
    if price == "free":
        courses = courses.filter(price=0)
    elif price == "paid":
        courses = courses.filter(price__gt=0)
    return render(request, 'courses/list.html', {
        'courses': courses,
        'categories': categories,
    })


def course_detail(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    lessons = course.lessons.all().order_by('order')
    is_enrolled = False
    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(
            student=request.user,
            course=course
        ).exists()
    return render(request, 'courses/detail.html', {
        'course': course,
        'lessons': lessons,
        'is_enrolled': is_enrolled,
    })


@login_required
def enroll_course(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    Enrollment.objects.get_or_create(
        student=request.user,
        course=course,
    )
    return redirect('course_detail', course_slug=course.slug)


@login_required
def lesson_detail(request, course_slug, lesson_slug):
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, slug=lesson_slug, course=course)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)
    total_lessons = course.lessons.count()
    completed = enrollment.completed_lessons.count()
    progress = int((completed / total_lessons) * 100) if total_lessons > 0 else 0
    lessons = course.lessons.all().order_by('order')
    prev_lesson = lessons.filter(order__lt=lesson.order).last()
    next_lesson = lessons.filter(order__gt=lesson.order).first()
    return render(request, 'lessons/detail.html', {
        'course': course,
        'lesson': lesson,
        'enrollment': enrollment,
        'progress': progress,
        'lessons': lessons,
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
    })


@login_required
def mark_lesson_complete(request, course_slug, lesson_slug):
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, slug=lesson_slug, course=course)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)
    enrollment.completed_lessons.add(lesson)
    total_lessons = course.lessons.count()
    if enrollment.completed_lessons.count() == total_lessons:
        enrollment.completed = True
        enrollment.save()
    return redirect('lesson_detail', course_slug=course.slug, lesson_slug=lesson.slug)


@login_required
def dashboard(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    return render(request, 'users/dashboard.html', {
        'enrollments': enrollments
    })