from django.contrib import admin
from .models import Category, Course, Lesson, Enrollment, Payment, Subscription


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description_short']
    search_fields = ['name']

    def description_short(self, obj):
        return (obj.description[:50] + '...') if getattr(obj, 'description', None) else ''
    description_short.short_description = 'Описание'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_instructor', 'get_category', 'price', 'get_duration', 'created']
    list_filter = ['category', 'created']
    search_fields = ['title', 'description']
    readonly_fields = ['created']

    def get_instructor(self, obj):
        return obj.author.username if obj.author else '—'
    get_instructor.short_description = 'Инструктор'

    def get_category(self, obj):
        return obj.category.name if obj.category else '—'
    get_category.short_description = 'Категория'

    def get_duration(self, obj):
        return f"{obj.lessons.count()} уроков"
    get_duration.short_description = 'Длительность'


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_course', 'order']
    list_filter = ['course']
    ordering = ['course', 'order']
    search_fields = ['title', 'content']

    def get_course(self, obj):
        return obj.course.title if obj.course else '—'
    get_course.short_description = 'Курс'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['get_student', 'get_course', 'get_date_joined', 'completed']
    list_filter = ['completed', 'date_joined']
    search_fields = ['student__username', 'course__title']
    readonly_fields = ['date_joined']

    def get_student(self, obj):
        return obj.student.username if obj.student else '—'
    get_student.short_description = 'Студент'

    def get_course(self, obj):
        return obj.course.title if obj.course else '—'
    get_course.short_description = 'Курс'

    def get_date_joined(self, obj):
        return obj.date_joined.strftime('%d.%m.%Y %H:%M') if obj.date_joined else '—'
    get_date_joined.short_description = 'Записан'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'amount', 'success', 'created']
    list_filter = ['success', 'created']
    search_fields = ['user__username', 'course__title']
    readonly_fields = ['created']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'start_date', 'end_date', 'active']
    list_filter = ['active']
    search_fields = ['user__username']
    readonly_fields = ['start_date']
