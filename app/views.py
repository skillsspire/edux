from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import HttpResponse
from .models import Course, Category, Lesson, Enrollment


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

    # поиск
    query = request.GET.get('q')
    if query:
        courses = courses.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )

    # фильтры
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
    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=course,
    )
    return redirect('course_detail', course_slug=course.slug)


@login_required
def lesson_detail(request, course_slug, lesson_slug):
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, slug=lesson_slug, course=course)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    return render(request, 'lessons/detail.html', {
        'course': course,
        'lesson': lesson,
        'enrollment': enrollment,
    })


@login_required
def mark_lesson_complete(request, enrollment_id, lesson_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, student=request.user)
    lesson = get_object_or_404(Lesson, id=lesson_id)

    enrollment.completed_lessons.add(lesson)

    total_lessons = enrollment.course.lessons.count()
    if enrollment.completed_lessons.count() == total_lessons:
        enrollment.completed = True
        enrollment.save()

        # если сигналов нет — можно создать сертификат здесь
        # from .models import Certificate
        # if not hasattr(enrollment, "certificate"):
        #     Certificate.objects.create(enrollment=enrollment)

    return redirect('lesson_detail', course_slug=enrollment.course.slug, lesson_slug=lesson.slug)


@login_required
def dashboard(request):
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    return render(request, 'users/dashboard.html', {
        'enrollments': enrollments
    })
