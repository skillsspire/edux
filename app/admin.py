from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timezone import now
from django.http import HttpResponse
from django.db.models import Q
import csv

from .models import Category, Course, Lesson, Enrollment, Payment, Subscription, InstructorProfile, Review, Wishlist, Module, LessonProgress, ContactMessage

admin.site.empty_value_display = '—'

class PriceRangeFilter(admin.SimpleListFilter):
    title = 'Цена'
    parameter_name = 'price_range'

    def lookups(self, request, model_admin):
        return [
            ('free', 'Бесплатно'),
            ('lt100', '< 100'),
            ('100-500', '100–500'),
            ('gt500', '> 500'),
        ]

    def queryset(self, request, qs):
        value = self.value()
        if value == 'free':
            return qs.filter(price=0)
        if value == 'lt100':
            return qs.filter(price__lt=100)
        if value == '100-500':
            return qs.filter(price__gte=100, price__lte=500)
        if value == 'gt500':
            return qs.filter(price__gt=500)
        return qs

class ActiveSubscriptionFilter(admin.SimpleListFilter):
    title = 'Статус подписки'
    parameter_name = 'sub_active'

    def lookups(self, request, model_admin):
        return [('active', 'Активна'), ('expired', 'Истекла')]

    def queryset(self, request, qs):
        value = self.value()
        if value == 'active':
            return qs.filter(active=True, end_date__gte=now().date())
        if value == 'expired':
            return qs.filter(Q(active=False) | Q(end_date__lt=now().date()))
        return qs

class ModuleInline(admin.TabularInline):
    model = Module
    fields = ['title', 'order', 'is_active']
    extra = 0
    ordering = ['order']
    show_change_link = True

class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    fields = ['user', 'completed', 'enrolled_at']
    readonly_fields = ['enrolled_at']
    extra = 0
    autocomplete_fields = ['user']
    show_change_link = True

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description_short', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    list_editable = ['is_active']

    @admin.display(description='Описание')
    def description_short(self, obj):
        desc = getattr(obj, 'description', '')
        return (desc[:50] + '...') if desc else ''

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title_link', 'instructor', 'category', 'price', 'status', 'created_at']
    list_display_links = ['title_link']
    list_filter = ['category', 'status', 'level', 'is_featured', 'created_at']
    search_fields = ['title', 'short_description']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['instructor', 'category']
    list_select_related = ['instructor', 'category']
    date_hierarchy = 'created_at'
    list_per_page = 50
    inlines = [ModuleInline, EnrollmentInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('instructor', 'category').prefetch_related('modules')

    @admin.display(description='Курс', ordering='title')
    def title_link(self, obj):
        url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.title)

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'module', 'order', 'is_active']
    list_filter = ['is_active', 'is_free', 'module__course']
    ordering = ['module__course__title', 'module__order', 'order']
    search_fields = ['title', 'content']
    autocomplete_fields = ['module']
    list_select_related = ['module__course']

@admin.action(description='Отметить выбранные записи как завершённые')
def mark_completed(modeladmin, request, queryset):
    updated = queryset.update(completed=True)
    messages.success(request, f'Отмечено завершёнными: {updated}')

@admin.action(description='Экспортировать в CSV')
def export_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=enrollments_export.csv'
    writer = csv.writer(response)
    writer.writerow(['user', 'course', 'completed', 'enrolled_at'])
    for e in queryset.select_related('user', 'course'):
        writer.writerow([
            getattr(e.user, 'username', ''),
            getattr(e.course, 'title', ''),
            '1' if e.completed else '0',
            e.enrolled_at.strftime('%Y-%m-%d %H:%M:%S') if e.enrolled_at else ''
        ])
    return response

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'enrolled_at', 'completed']
    list_filter = ['completed', 'enrolled_at']
    search_fields = ['user__username', 'course__title']
    readonly_fields = ['enrolled_at']
    autocomplete_fields = ['user', 'course']
    list_select_related = ['user', 'course']
    date_hierarchy = 'enrolled_at'
    actions = [mark_completed, export_csv]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'course_link', 'amount', 'status', 'created']  # ← ИЗМЕНИТЬ success на status
    list_filter = ['status', 'created']  # ← ИЗМЕНИТЬ success на status
    search_fields = ['user__username', 'course__title']
    autocomplete_fields = ['user', 'course']
    list_select_related = ['user', 'course']
    readonly_fields = ['user', 'course', 'amount', 'status', 'created']  # ← ИЗМЕНИТЬ success на status
    date_hierarchy = 'created'

    @admin.display(description='Курс')
    def course_link(self, obj):
        if obj.course:
            url = reverse(f'admin:{obj.course._meta.app_label}_{obj.course._meta.model_name}_change', args=[obj.course.pk])
            return format_html('<a href="{}">{}</a>', url, obj.course.title)
        return '—'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_change_permission(self, request, obj=None):
        if request.method in ('POST',):
            return False
        return super().has_change_permission(request, obj)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'start_date', 'end_date', 'active']
    list_filter = [ActiveSubscriptionFilter]
    search_fields = ['user__username']
    readonly_fields = ['start_date']
    autocomplete_fields = ['user']
    date_hierarchy = 'start_date'

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['name', 'email', 'subject']
    readonly_fields = ['created_at']
    list_editable = ['is_read']
    date_hierarchy = 'created_at'

@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialization', 'experience', 'is_approved']
    list_filter = ['is_approved']
    search_fields = ['user__username', 'specialization']
    autocomplete_fields = ['user']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'rating', 'created_at', 'is_active']
    list_filter = ['rating', 'is_active', 'created_at']
    search_fields = ['user__username', 'course__title']
    autocomplete_fields = ['user', 'course']

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'added_at']
    list_filter = ['added_at']
    search_fields = ['user__username', 'course__title']
    autocomplete_fields = ['user', 'course']

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'is_active']
    list_filter = ['is_active', 'course']
    search_fields = ['title', 'course__title']
    ordering = ['course', 'order']
    autocomplete_fields = ['course']

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'lesson', 'completed', 'last_accessed']
    list_filter = ['completed', 'last_accessed']
    search_fields = ['user__username', 'lesson__title']
    autocomplete_fields = ['user', 'lesson']
