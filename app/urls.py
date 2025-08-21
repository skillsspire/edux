from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from .models import Category, Course, Lesson, Enrollment  # Импортируем из models.py


# View функции
def home(request):
    categories = Category.objects.all()
    featured_courses = Course.objects.all()[:6]
    return render(request, 'home.html', {
        'categories': categories,
        'featured_courses': featured_courses
    })


def course_list(request):
    courses = Course.objects.all()
    return render(request, 'courses/list.html', {'courses': courses})


def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    is_enrolled = False
    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(
            student=request.user,
            course=course
        ).exists()

    return render(request, 'courses/detail.html', {
        'course': course,
        'is_enrolled': is_enrolled
    })


@login_required
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=course
    )
    return redirect('course_detail', course_id=course_id)


@login_required
def my_courses(request):
    enrollments = Enrollment.objects.filter(student=request.user)
    return render(request, 'courses/my_courses.html', {'enrollments': enrollments})


@login_required
def course_lesson(request, course_id, lesson_id):
    course = get_object_or_404(Course, id=course_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)

    enrollment = Enrollment.objects.filter(
        student=request.user,
        course=course
    ).first()

    if not enrollment:
        return redirect('course_detail', course_id=course_id)

    return render(request, 'courses/lesson.html', {
        'course': course,
        'lesson': lesson
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('courses/', course_list, name='course_list'),
    path('courses/<int:course_id>/', course_detail, name='course_detail'),
    path('courses/<int:course_id>/enroll/', enroll_course, name='enroll_course'),
    path('my-courses/', my_courses, name='my_courses'),
    path('courses/<int:course_id>/lesson/<int:lesson_id>/',
         course_lesson, name='course_lesson'),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)