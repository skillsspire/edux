# admin.py
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timezone import now
from django.http import HttpResponse
from django.db.models import Count, Q
import csv

from .models import Category, Course, Lesson, Enrollment, Payment, Subscription


# =========================
# Глобальные мелочи
# =========================
admin.site.empty_value_display = '—'


# =========================
# Вспомогательные фильтры
# =========================
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
        v = self.value()
        if v == 'free':
            return qs.filter(price=0)
        if v == 'lt100':
            return qs.filter(price__lt=100)
        if v == '100-500':
            return qs.filter(price__gte=100, price__lte=500)
        if v == 'gt500':
            return qs.filter(price__gt=500)
        return qs


class ActiveSubscriptionFilter(admin.SimpleListFilter):
    title = 'Статус подписки'
    parameter_name = 'sub_active'

    def lookups(self, request, model_admin):
        return [('active', 'Активна'), ('expired', 'Истекла')]

    def queryset(self, request, qs):
        if self.value() == 'active':
            return qs.filter(active=True, end_date__gte=now().date())
        if self.value() == 'expired':
            return qs.filter(Q(active=False) | Q(end_date__lt=now().date()))
        return qs


# =========================
# Инлайны
# =========================
class LessonInline(admin.TabularInline):
    model = Lesson
    fields = ['title', 'order']
    extra = 0
    ordering = ['order']
    show_change_link = True


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    fields = ['student', 'completed', 'date_joined']
    readonly_fields = ['date_joined']
    extra = 0
    autocomplete_fields = ['student']
    show_change_link = True


# =========================
# Category
# =========================
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description_short']
    search_fields = ['name']

    @admin.display(description='Описание')
    def description_short(self, obj):
        desc = getattr(obj, 'description', '')
        return (desc[:50] + '...') if desc else ''


# =========================
# Course
# =========================
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title_link', 'get_instructor', 'get_category', 'price', 'lessons_count', 'created']
    list_display_links = ['title_link']
    list_filter = ['category', 'created', PriceRangeFilter]
    search_fields = ['title', 'description']
    readonly_fields = ['created']
    autocomplete_fields = ['author', 'category']
    list_select_related = ['author', 'category']
    date_hierarchy = 'created'
    list_per_page = 50
    inlines = [LessonInline, EnrollmentInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('author', 'category').annotate(_lessons_count=Count('lessons'))

    @admin.display(description='Курс', ordering='title')
    def title_link(self, obj):
        # Кликабельная ссылка на изменение курса
        url = reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.title)

    @admin.display(description='Инструктор', ordering='author__username')
    def get_instructor(self, obj):
        return obj.author.username if obj.author else '—'

    @admin.display(description='Категория', ordering='category__name')
    def get_category(self, obj):
        return obj.category.name if obj.category else '—'

    @admin.display(description='Длительность', ordering='_lessons_count')
    def lessons_count(self, obj):
        return f'{obj._lessons_count} уроков'


# =========================
# Lesson
# =========================
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'get_course', 'order']
    list_filter = ['course']
    ordering = ['course', 'order']
    search_fields = ['title', 'content']
    autocomplete_fields = ['course']
    list_select_related = ['course']

    @admin.display(description='Курс', ordering='course__title')
    def get_course(self, obj):
        return obj.course.title if obj.course else '—'


# =========================
# Массовые действия Enrollment
# =========================
@admin.action(description='Отметить выбранные записи как завершённые')
def mark_completed(modeladmin, request, queryset):
    updated = queryset.update(completed=True)
    messages.success(request, f'Отмечено завершёнными: {updated}')


@admin.action(description='Экспортировать в CSV')
def export_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=enrollments_export.csv'
    writer = csv.writer(response)
    writer.writerow(['student', 'course', 'completed', 'date_joined'])
    for e in queryset.select_related('student', 'course'):
        writer.writerow([
            getattr(e.student, 'username', ''),
            getattr(e.course, 'title', ''),
            '1' if e.completed else '0',
            e.date_joined.strftime('%Y-%m-%d %H:%M:%S') if e.date_joined else ''
        ])
    return response


# =========================
# Enrollment
# =========================
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['get_student', 'get_course', 'get_date_joined', 'completed']
    list_filter = ['completed', 'date_joined']
    search_fields = ['student__username', 'course__title']
    readonly_fields = ['date_joined']
    autocomplete_fields = ['student', 'course']
    list_select_related = ['student', 'course']
    date_hierarchy = 'date_joined'
    actions = [mark_completed, export_csv]

    @admin.display(description='Студент', ordering='student__username')
    def get_student(self, obj):
        return obj.student.username if obj.student else '—'

    @admin.display(description='Курс', ordering='course__title')
    def get_course(self, obj):
        return obj.course.title if obj.course else '—'

    @admin.display(description='Записан', ordering='date_joined')
    def get_date_joined(self, obj):
        return obj.date_joined.strftime('%d.%m.%Y %H:%M') if obj.date_joined else '—'


# =========================
# Payment (read-only, создаются сайтом/платёжкой)
# =========================
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """
    Админка платежей только для просмотра:
    - нельзя добавить/удалить/редактировать записи вручную
    - считаем, что записи создаются автоматически
    """
    list_display = ['user', 'course_link', 'amount', 'success', 'created']
    list_filter = ['success', 'created']
    search_fields = ['user__username', 'course__title']
    autocomplete_fields = ['user', 'course']
    list_select_related = ['user', 'course']
    readonly_fields = []  # заполним динамически ниже
    date_hierarchy = 'created'

    def get_readonly_fields(self, request, obj=None):
        # Делаем read-only все поля модели
        return [f.name for f in self.model._meta.fields]

    @admin.display(description='Курс')
    def course_link(self, obj):
        if obj.course_id and obj.course:
            url = reverse(f'admin:{obj.course._meta.app_label}_{obj.course._meta.model_name}_change', args=[obj.course_id])
            return format_html('<a href="{}">{}</a>', url, obj.course.title)
        return '—'

    # Запрещаем добавление/удаление/массовое удаление
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    # На всякий случай: не даём сохранять изменения через админ
    def has_change_permission(self, request, obj=None):
        # Разрешаем открывать страницу просмотра (detail), но не сохранять.
        if request.method in ('POST',):
            return False
        return super().has_change_permission(request, obj)


# =========================
# Subscription
# =========================
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'start_date', 'end_date', 'active']
    list_filter = [ActiveSubscriptionFilter]
    search_fields = ['user__username']
    readonly_fields = ['start_date']
    autocomplete_fields = ['user']
    date_hierarchy = 'start_date'
