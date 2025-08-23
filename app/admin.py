from django.contrib import admin
from .models import Category, Course, Lesson, Enrollment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description_short']
    search_fields = ['name']

    def description_short(self, obj):
        return obj.description[:50] + '...' if obj.description else ''

    description_short.short_description = 'Описание'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_instructor', 'get_category', 'price', 'get_duration', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at']

    def get_instructor(self, obj):
        return obj.instructor.username

    get_instructor.short_description = 'Инструктор'

    def get_category(self, obj):
        return obj.category.name

    get_category.short_description = 'Категория'

    def get_duration(self, obj):
        return f"{obj.duration} часов"

    get_duration.short_description = 'Длительность'


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_course', 'order']
    list_filter = ['course']
    ordering = ['course', 'order']
    search_fields = ['title', 'content']

    def get_course(self, obj):
        return obj.course.title

    get_course.short_description = 'Курс'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['get_student', 'get_course', 'get_enrolled_at', 'completed']
    list_filter = ['completed', 'enrolled_at']
    search_fields = ['student__username', 'course__title']
    readonly_fields = ['enrolled_at']

    def get_student(self, obj):
        return obj.student.username

    get_student.short_description = 'Студент'

    def get_course(self, obj):
        return obj.course.title

    get_course.short_description = 'Курс'

    def get_enrolled_at(self, obj):
        return obj.enrolled_at.strftime('%d.%m.%Y %H:%M')

    get_enrolled_at.short_description = 'Записан'