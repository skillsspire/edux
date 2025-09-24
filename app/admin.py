from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Category,
    InstructorProfile,
    Course,
    Module,
    Lesson,
    LessonProgress,
    Enrollment,
    Review,
    Wishlist,
    Payment,
    Subscription,
    ContactMessage,
)

# Константы для единообразия
IMAGE_PREVIEW_SIZE = {"width": 100, "height": 70}
VIDEO_PREVIEW_SIZE = {"width": 180, "height": 100}
DEFAULT_EMPTY_VALUE = "—"


class SafeFieldMixin:
    """
    Миксин для безопасного доступа к полям моделей с разными структурами
    """
    
    def _first_attr(self, obj, *names, default=DEFAULT_EMPTY_VALUE):
        """Возвращает первое найденное непустое значение атрибута в виде строки"""
        for name in names:
            if hasattr(obj, name):
                val = getattr(obj, name)
                if val is not None and val != "":
                    return str(val)
        return default

    def _first_value(self, obj, *names, default=None):
        """Возвращает первое найденное значение атрибута как есть"""
        for name in names:
            if hasattr(obj, name):
                val = getattr(obj, name)
                if val is not None:
                    return val
        return default


# ---------- Inline Admin Classes ----------

class ModuleInline(admin.TabularInline):
    """Inline для модулей курса"""
    model = Module
    extra = 0
    fields = ("title", "order", "is_active")
    show_change_link = True


class LessonInline(admin.TabularInline):
    """Inline для уроков модуля"""
    model = Lesson
    extra = 0
    fields = ("title", "slug", "order", "is_active", "is_free")
    prepopulated_fields = {"slug": ("title",)}
    show_change_link = True


# ---------- Category Admin ----------

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Админка для категорий SkillsSpire"""
    
    list_display = ("name", "slug", "is_active", "order", "courses_count")
    list_editable = ("is_active", "order")
    search_fields = ("name", "description")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 25

    def courses_count(self, obj):
        """Количество курсов в категории"""
        return obj.course_set.count()
    courses_count.short_description = "Курсов"


# ---------- Instructor Profile Admin ----------

@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin, SafeFieldMixin):
    """Админка для профилей инструкторов SkillsSpire"""
    
    list_display = (
        "user_display",
        "is_approved_display",
        "specialization",
        "experience_display",
        "courses_count",
        "created_display"
    )
    list_filter = ("is_approved", "created_at")
    search_fields = ("user__username", "user__first_name", "user__last_name", "specialization")
    readonly_fields = ("courses_count", "created_at", "updated_at", "user_display")
    list_per_page = 25

    def user_display(self, obj):
        """Отображение пользователя"""
        if obj.user:
            return f"{obj.user.get_full_name() or obj.user.username} ({obj.user.email})"
        return DEFAULT_EMPTY_VALUE
    user_display.short_description = "Пользователь"

    def is_approved_display(self, obj):
        """Отображение статуса одобрения"""
        return "✅ Одобрен" if obj.is_approved else "⏳ На рассмотрении"
    is_approved_display.short_description = "Статус"
    is_approved_display.admin_order_field = "is_approved"

    def experience_display(self, obj):
        """Отображение опыта"""
        if obj.experience:
            return f"{obj.experience} лет"
        return DEFAULT_EMPTY_VALUE
    experience_display.short_description = "Опыт"

    def courses_count(self, obj):
        """Количество курсов инструктора"""
        return obj.course_set.count()
    courses_count.short_description = "Курсов"

    def created_display(self, obj):
        """Отображение даты создания"""
        return obj.created_at.strftime("%d.%m.%Y %H:%M") if obj.created_at else DEFAULT_EMPTY_VALUE
    created_display.short_description = "Создан"


# ---------- Course Admin ----------

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin, SafeFieldMixin):
    """Админка для курсов SkillsSpire"""
    
    list_display = (
        "image_preview",
        "title",
        "category",
        "instructor_display",
        "status_display",
        "price_kzt",
        "students_count",
        "rating_display",
        "created_display",
    )
    list_display_links = ("image_preview", "title")
    list_filter = ("category", "status", "level", "is_featured", "is_popular", "created_at")
    search_fields = ("title", "short_description", "description")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category", "instructor", "students")
    readonly_fields = (
        "students_count", "reviews_count", "rating", "created_at", "updated_at",
        "image_preview", "rating_display"
    )
    inlines = [ModuleInline]
    ordering = ("-created_at",)
    list_per_page = 25
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("title", "slug", "category", "instructor", "short_description", "description")
        }),
        ("Изображение", {
            "fields": ("image", "image_preview")
        }),
        ("Детали курса", {
            "fields": (("price", "level", "status"), ("duration", "language"))
        }),
        ("Статусы", {
            "fields": (("is_featured", "is_popular"),)
        }),
        ("Статистика", {
            "fields": (("students_count", "reviews_count", "rating_display"),),
            "classes": ("collapse",)
        }),
        ("Даты", {
            "fields": (("created_at", "updated_at"),),
            "classes": ("collapse",)
        })
    )

    def instructor_display(self, obj):
        """Отображение инструктора"""
        if obj.instructor and obj.instructor.user:
            return obj.instructor.user.get_full_name() or obj.instructor.user.username
        return DEFAULT_EMPTY_VALUE
    instructor_display.short_description = "Инструктор"

    def status_display(self, obj):
        """Отображение статуса курса"""
        status_map = {
            "draft": "📝 Черновик",
            "published": "✅ Опубликован",
            "archived": "🗄️ В архиве"
        }
        return status_map.get(obj.status, obj.status)
    status_display.short_description = "Статус"

    def price_kzt(self, obj):
        """Отображение цены в тенге"""
        if obj.price is None:
            return DEFAULT_EMPTY_VALUE
        try:
            return f"{int(obj.price):,} ₸".replace(",", " ")
        except (ValueError, TypeError):
            return str(obj.price)
    price_kzt.short_description = "Цена"
    price_kzt.admin_order_field = "price"

    def rating_display(self, obj):
        """Отображение рейтинга"""
        if obj.rating is None:
            return DEFAULT_EMPTY_VALUE
        return f"{obj.rating:.1f} ⭐"
    rating_display.short_description = "Рейтинг"

    def created_display(self, obj):
        """Отображение даты создания"""
        return obj.created_at.strftime("%d.%m.%Y") if obj.created_at else DEFAULT_EMPTY_VALUE
    created_display.short_description = "Создан"

    def image_preview(self, obj):
        """Превью изображения курса"""
        if obj.image and hasattr(obj.image, "url"):
            try:
                return format_html(
                    '<img src="{}" width="{}" height="{}" style="object-fit:cover;border-radius:6px;">',
                    obj.image.url, IMAGE_PREVIEW_SIZE["width"], IMAGE_PREVIEW_SIZE["height"]
                )
            except Exception:
                pass
        return DEFAULT_EMPTY_VALUE
    image_preview.short_description = "Превью"


# ---------- Module Admin ----------

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    """Админка для модулей SkillsSpire"""
    
    list_display = ("title", "course", "order", "lessons_count", "is_active")
    list_filter = ("is_active", "course")
    search_fields = ("title", "description", "course__title")
    autocomplete_fields = ("course",)
    inlines = [LessonInline]
    ordering = ("course", "order")
    list_per_page = 25

    def lessons_count(self, obj):
        """Количество уроков в модуле"""
        return obj.lesson_set.count()
    lessons_count.short_description = "Уроков"

    def get_queryset(self, request):
        """Оптимизация запроса с prefetch_related"""
        return super().get_queryset(request).prefetch_related("lesson_set")


# ---------- Lesson Admin ----------

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """Админка для уроков SkillsSpire"""
    
    list_display = ("title", "module", "course_display", "order", "is_active", "is_free", "video_preview")
    list_filter = ("is_active", "is_free", "module__course")
    search_fields = ("title", "content", "module__title", "module__course__title")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("module",)
    readonly_fields = ("video_preview",)
    ordering = ("module__course", "module__order", "order")
    list_per_page = 25
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("title", "slug", "module", "order")
        }),
        ("Содержание", {
            "fields": ("content", "video_url", "video_preview")
        }),
        ("Настройки", {
            "fields": (("is_active", "is_free"),)
        }),
        ("Дополнительно", {
            "fields": ("resources",),
            "classes": ("collapse",)
        })
    )

    def course_display(self, obj):
        """Отображение курса урока"""
        return obj.module.course.title if obj.module and obj.module.course else DEFAULT_EMPTY_VALUE
    course_display.short_description = "Курс"
    course_display.admin_order_field = "module__course__title"

    def video_preview(self, obj):
        """Превью видео"""
        if not obj.video_url:
            return DEFAULT_EMPTY_VALUE
        try:
            if "youtube" in obj.video_url:
                embed_url = obj.video_url.replace("watch?v=", "embed/")
                return format_html(
                    '<iframe width="{}" height="{}" src="{}" frameborder="0" allowfullscreen></iframe>',
                    VIDEO_PREVIEW_SIZE["width"], VIDEO_PREVIEW_SIZE["height"], embed_url
                )
            elif "vimeo" in obj.video_url:
                return format_html(
                    '<iframe src="{}" width="{}" height="{}" frameborder="0" allowfullscreen></iframe>',
                    obj.video_url, VIDEO_PREVIEW_SIZE["width"], VIDEO_PREVIEW_SIZE["height"]
                )
        except Exception:
            pass
        return format_html('<a href="{}" target="_blank">🎬 Смотреть видео</a>', obj.video_url)
    video_preview.short_description = "Видео"

    def get_queryset(self, request):
        """Оптимизация запроса с select_related"""
        return super().get_queryset(request).select_related("module__course")


# ---------- Lesson Progress Admin ----------

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    """Админка для прогресса уроков SkillsSpire"""
    
    list_display = ("user_display", "lesson_display", "course_display", "is_completed", "updated_at")
    list_filter = ("is_completed", "updated_at")
    search_fields = ("user__username", "lesson__title", "lesson__module__course__title")
    autocomplete_fields = ("user", "lesson")
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25

    def user_display(self, obj):
        """Отображение пользователя"""
        return obj.user.username if obj.user else DEFAULT_EMPTY_VALUE
    user_display.short_description = "Пользователь"

    def lesson_display(self, obj):
        """Отображение урока"""
        return obj.lesson.title if obj.lesson else DEFAULT_EMPTY_VALUE
    lesson_display.short_description = "Урок"

    def course_display(self, obj):
        """Отображение курса"""
        if obj.lesson and obj.lesson.module and obj.lesson.module.course:
            return obj.lesson.module.course.title
        return DEFAULT_EMPTY_VALUE
    course_display.short_description = "Курс"


# ---------- Enrollment Admin ----------

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Админка для записей на курсы SkillsSpire"""
    
    list_display = ("user_display", "course", "enrolled_at", "completed", "completed_at", "progress_display")
    list_filter = ("completed", "enrolled_at")
    search_fields = ("user__username", "course__title")
    autocomplete_fields = ("user", "course")
    readonly_fields = ("enrolled_at",)
    list_per_page = 25

    def user_display(self, obj):
        """Отображение пользователя"""
        return obj.user.username if obj.user else DEFAULT_EMPTY_VALUE
    user_display.short_description = "Пользователь"

    def progress_display(self, obj):
        """Отображение прогресса"""
        # Здесь можно добавить логику расчета прогресса
        return "0%"  # Заглушка - нужно реализовать логику
    progress_display.short_description = "Прогресс"


# ---------- Review Admin ----------

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Админка для отзывов SkillsSpire"""
    
    list_display = ("user_display", "course", "rating_display", "short_comment", "is_active", "created_at")
    list_filter = ("rating", "is_active", "created_at")
    search_fields = ("user__username", "course__title", "comment")
    autocomplete_fields = ("user", "course")
    list_per_page = 25
    actions = ["activate_reviews", "deactivate_reviews"]

    def user_display(self, obj):
        """Отображение пользователя"""
        return obj.user.username if obj.user else DEFAULT_EMPTY_VALUE
    user_display.short_description = "Пользователь"

    def rating_display(self, obj):
        """Отображение рейтинга"""
        return "⭐" * int(obj.rating) if obj.rating else "—"
    rating_display.short_description = "Оценка"

    def short_comment(self, obj):
        """Сокращенный комментарий"""
        if obj.comment:
            return (obj.comment[:60] + "…") if len(obj.comment) > 60 else obj.comment
        return DEFAULT_EMPTY_VALUE
    short_comment.short_description = "Комментарий"

    def activate_reviews(self, request, queryset):
        """Активировать выбранные отзывы"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Активировано {updated} отзывов")
    activate_reviews.short_description = "Активировать выбранные отзывы"

    def deactivate_reviews(self, request, queryset):
        """Деактивировать выбранные отзывы"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано {updated} отзывов")
    deactivate_reviews.short_description = "Деактивировать выбранные отзывы"


# ---------- Остальные админки (краткая версия) ----------

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "added_at")
    list_filter = ("added_at",)
    search_fields = ("user__username", "course__title")
    autocomplete_fields = ("user", "course")
    list_per_page = 25


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin, SafeFieldMixin):
    list_display = ("user", "course", "amount_display", "status_display", "created_display")
    list_filter = ("status", "created")
    search_fields = ("user__username", "course__title", "kaspi_invoice_id")
    autocomplete_fields = ("user", "course")
    readonly_fields = ("created", "updated")
    list_per_page = 25

    def amount_display(self, obj):
        return f"{obj.amount:,} ₸".replace(",", " ") if obj.amount else DEFAULT_EMPTY_VALUE
    amount_display.short_description = "Сумма"

    def status_display(self, obj):
        status_map = {
            "pending": "⏳ Ожидание",
            "completed": "✅ Успешно",
            "failed": "❌ Ошибка",
            "canceled": "🚫 Отменен"
        }
        return status_map.get(obj.status, obj.status)
    status_display.short_description = "Статус"

    def created_display(self, obj):
        return obj.created.strftime("%d.%m.%Y %H:%M") if obj.created else DEFAULT_EMPTY_VALUE
    created_display.short_description = "Создан"


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "start_date", "end_date", "active_display", "days_remaining")
    list_filter = ("active", "start_date")
    search_fields = ("user__username",)
    autocomplete_fields = ("user",)
    list_per_page = 25

    def active_display(self, obj):
        return "✅ Активна" if obj.active else "❌ Неактивна"
    active_display.short_description = "Статус"

    def days_remaining(self, obj):
        if obj.active and obj.end_date:
            from django.utils import timezone
            remaining = (obj.end_date - timezone.now().date()).days
            return f"{remaining} дн." if remaining > 0 else "Истек"
        return DEFAULT_EMPTY_VALUE
    days_remaining.short_description = "Осталось"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_read_display", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("created_at",)
    list_per_page = 25
    actions = ["mark_as_read", "mark_as_unread"]

    def is_read_display(self, obj):
        return "✅ Прочитано" if obj.is_read else "📨 Новое"
    is_read_display.short_description = "Статус"

    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"Помечено как прочитано: {updated} сообщений")
    mark_as_read.short_description = "Пометить как прочитанные"

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"Помечено как непрочитано: {updated} сообщений")
    mark_as_unread.short_description = "Пометить как непрочитанные"


# ---------- Настройки админки SkillsSpire ----------

admin.site.site_header = "🏔️ SkillsSpire — Панель управления"
admin.site.site_title = "SkillsSpire Admin"
admin.site.index_title = "Управление образовательной платформой SkillsSpire"