from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from .models import Course, Category, Lesson, Enrollment

def home(request):
    # Получаем популярные курсы (по количеству записей)
    popular_courses = Course.objects.annotate(num_students=Count('enrollments')).order_by('-num_students')[:5]
    # Получаем все категории
    categories = Category.objects.all()

    context = {
        'popular_courses': popular_courses,
        'categories': categories,
    }
    return render(request, 'home.html', context)

def courses_list(request):
    # Получаем все курсы
    courses = Course.objects.all()
    # Обрабатываем поисковый запрос
    query = request.GET.get('q')
    if query:
        courses = courses.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )
    # Обрабатываем фильтр по категории
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        courses = courses.filter(category=category)

    context = {
        'courses': courses,
        'categories': Category.objects.all(), # Передаем все категории для отображения в фильтре
    }
    return render(request, 'courses/list.html', context)

def course_detail(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    # Проверяем, записан ли уже пользователь на курс
    is_enrolled = False
    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(student=request.user, course=course).exists()

    context = {
        'course': course,
        'is_enrolled': is_enrolled,
        'lessons': course.lessons.all().order_by('order') # Упорядочиваем уроки
    }
    return render(request, 'courses/detail.html', context)

@login_required
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    # Создаем запись о записи на курс, если ее еще нет
    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=course,
    )
    # Перенаправляем на страницу курса
    return redirect('course_detail', course_slug=course.slug)

@login_required
def lesson_detail(request, course_slug, lesson_slug):
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, slug=lesson_slug, course=course)
    # Проверяем, записан ли пользователь на курс
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    context = {
        'course': course,
        'lesson': lesson,
        'enrollment': enrollment,
    }
    return render(request, 'lessons/detail.html', context)

@login_required
def mark_lesson_complete(request, enrollment_id, lesson_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id, student=request.user)
    lesson = get_object_or_404(Lesson, id=lesson_id)
    # Добавляем урок в список завершенных для этой записи
    enrollment.completed_lessons.add(lesson)
    # Проверяем, завершен ли теперь весь курс
    total_lessons = enrollment.course.lessons.count()
    if enrollment.completed_lessons.count() == total_lessons:
        enrollment.completed = True
        enrollment.save()
        # TODO: Здесь позже будет триггер на создание сертификата
    return redirect('lesson_detail', course_slug=enrollment.course.slug, lesson_slug=lesson.slug)

@login_required
def dashboard(request):
    # Получаем все записи пользователя на курсы
    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    context = {
        'enrollments': enrollments
    }
    return render(request, 'users/dashboard.html', context)