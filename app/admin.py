from django.contrib import admin
from .models import Category, Course, Lesson, Enrollment


# Регистрируем модели с кастомизацией
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description_short']
    search_fields = ['name']

    def description_short(self, obj):
        return obj.description[:50] + '...' if obj.description else ''

    description_short.short_description = 'Описание'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'category', 'price', 'duration']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'description']


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order']
    list_filter = ['course']
    ordering = ['course', 'order']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'enrolled_at', 'completed']
    list_filter = ['completed', 'enrolled_at']

# Альтернативный способ регистрации (если декораторы не работают)
# admin.site.register(Category, CategoryAdmin)
# admin.site.register(Course, CourseAdmin)
# admin.site.register(Lesson, LessonAdmin)
# admin.site.register(Enrollment, EnrollmentAdmin)