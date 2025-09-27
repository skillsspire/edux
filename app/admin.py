from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

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

IMAGE_PREVIEW_SIZE = {"width": 100, "height": 70}
VIDEO_PREVIEW_SIZE = {"width": 180, "height": 100}
DEFAULT_EMPTY_VALUE = "—"


# ---------------------------
# Inlines
# ---------------------------

class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    fields = ("title", "order", "is_active")
    show_change_link = True


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("title", "slug", "order", "is_active", "is_free")
    prepopulated_fields = {"slug": ("title",)}
    show_change_link = True


# ---------------------------
# Category
# ---------------------------

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "order", "courses_count")
    list_editable = ("is_active", "order")
    search_fields = ("name", "description")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}

    def courses_count(self, obj):
        return obj.courses.count()
    courses_count.short_description = "Курсов"


# ---------------------------
# Instructor
# ---------------------------

@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "specialization", "experience", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("user__username", "user__email", "specialization")
    readonly_fields = ("created_at", "updated_at")


# ---------------------------
# Course
# ---------------------------

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "image_preview",
        "title",
        "category",
        "instructor",
        "status",
        "price",
        "students_count",
        "rating",
        "created_at",
    )
    list_display_links = ("image_preview", "title")
    list_filter = ("category", "status", "level", "is_featured", "is_popular", "created_at")
    search_fields = ("title", "short_description", "description", "category__name", "instructor__username")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category", "instructor", "students")
    readonly_fields = ("students_count", "reviews_count", "rating", "created_at", "updated_at", "image_preview")
    inlines = [ModuleInline]
    ordering = ("-created_at",)
    list_select_related = ("category", "instructor")

    def image_preview(self, obj):
        # используем приоритетный display_image_url из модели, если есть
        url = getattr(obj, "display_image_url", None) or (obj.image.url if getattr(obj, "image", None) and hasattr(obj.image, "url") else None)
        if url:
            return format_html(
                '<img src="{}" width="{}" height="{}" style="object-fit:cover;border-radius:6px;">',
                url, IMAGE_PREVIEW_SIZE["width"], IMAGE_PREVIEW_SIZE["height"]
            )
        return DEFAULT_EMPTY_VALUE
    image_preview.short_description = "Превью"


# ---------------------------
# Module
# ---------------------------

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_active")
    list_filter = ("is_active", "course")
    search_fields = ("title", "description", "course__title")
    autocomplete_fields = ("course",)
    inlines = [LessonInline]
    ordering = ("course", "order")
    list_select_related = ("course",)


# ---------------------------
# Lesson
# ---------------------------

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "course_display", "order", "is_active", "is_free", "video_preview")
    list_filter = ("is_active", "is_free", "module__course")
    search_fields = ("title", "content", "module__title", "module__course__title")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("module",)
    readonly_fields = ("video_preview",)
    ordering = ("module__course", "module__order", "order")
    list_select_related = ("module", "module__course")

    def course_display(self, obj):
        return obj.module.course.title if obj.module and obj.module.course else DEFAULT_EMPTY_VALUE
    course_display.short_description = "Курс"

    def video_preview(self, obj):
        if not obj.video_url:
            return DEFAULT_EMPTY_VALUE
        try:
            url = str(obj.video_url)
            if "youtube.com/watch?v=" in url:
                url = url.replace("watch?v=", "embed/")
            if "youtube.com/embed/" in url or "player.vimeo.com" in url or "vimeo.com" in url:
                return format_html(
                    '<iframe width="{}" height="{}" src="{}" frameborder="0" allowfullscreen></iframe>',
                    VIDEO_PREVIEW_SIZE["width"], VIDEO_PREVIEW_SIZE["height"], url
                )
        except Exception:
            pass
        return format_html('<a href="{}" target="_blank">🎬 Смотреть видео</a>', obj.video_url)
    video_preview.short_description = "Видео"


# ---------------------------
# Lesson Progress
# ---------------------------

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "lesson", "is_completed", "percent", "updated_at")
    list_filter = ("is_completed", "updated_at")
    search_fields = ("user__username", "user__email", "lesson__title", "lesson__module__course__title")
    autocomplete_fields = ("user", "lesson")
    readonly_fields = ("updated_at",)
    ordering = ("-updated_at",)
    list_select_related = ("lesson", "lesson__module", "lesson__module__course", "user")


# ---------------------------
# Enrollment
# ---------------------------

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "enrolled_at", "completed", "completed_at")
    list_filter = ("completed", "enrolled_at")
    search_fields = ("user__username", "user__email", "course__title")
    autocomplete_fields = ("user", "course")
    readonly_fields = ("enrolled_at",)
    list_select_related = ("user", "course")


# ---------------------------
# Review
# ---------------------------

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "rating", "is_active", "created_at")
    list_filter = ("rating", "is_active", "created_at")
    search_fields = ("user__username", "user__email", "course__title", "comment", "name", "position")
    autocomplete_fields = ("user", "course")
    ordering = ("-created_at",)
    list_select_related = ("user", "course")


# ---------------------------
# Wishlist
# ---------------------------

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "added_at")
    list_filter = ("added_at",)
    search_fields = ("user__username", "user__email", "course__title")
    autocomplete_fields = ("user", "course")
    ordering = ("-added_at",)
    list_select_related = ("user", "course")


# ---------------------------
# Payment
# ---------------------------

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "amount", "status", "kaspi_invoice_id", "created")
    list_filter = ("status", "created")
    search_fields = ("user__username", "user__email", "course__title", "kaspi_invoice_id")
    autocomplete_fields = ("user", "course")
    ordering = ("-created",)
    list_select_related = ("user", "course")
    readonly_fields = ("created", "updated", "receipt_preview")

    actions = ("mark_success", "mark_failed")

    fieldsets = (
        (None, {
            "fields": ("user", "course", "amount", "status")
        }),
        ("Kaspi", {
            "fields": ("kaspi_invoice_id",),
        }),
        ("Служебное", {
            "fields": ("created", "updated"),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        # Если в модели есть поле receipt_file — добавим его и превью в форму
        if obj and hasattr(obj, "receipt_file"):
            return (
                (None, {"fields": ("user", "course", "amount", "status")}),
                ("Kaspi", {"fields": ("kaspi_invoice_id",)}),
                ("Чек", {"fields": ("receipt_file", "receipt_preview")}),
                ("Служебное", {"fields": ("created", "updated")}),
            )
        return super().get_fieldsets(request, obj)

    def receipt_preview(self, obj):
        if not hasattr(obj, "receipt_file"):
            return DEFAULT_EMPTY_VALUE
        f = getattr(obj, "receipt_file", None)
        if not f:
            return DEFAULT_EMPTY_VALUE
        name = getattr(f, "name", "") or ""
        url = getattr(f, "url", "") or ""
        if not url and name:
            # возможен случай Supabase без .url (на всякий)
            url = name
        if not url:
            return DEFAULT_EMPTY_VALUE

        lower = name.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return format_html('<img src="{}" style="max-width:280px;max-height:180px;object-fit:contain;border-radius:6px;">', url)
        if lower.endswith((".pdf", ".mp4", ".mov", ".avi", ".mkv", ".webm")):
            return format_html('<a href="{}" target="_blank" rel="noopener">Открыть файл чека</a>', url)
        return format_html('<a href="{}" target="_blank" rel="noopener">Файл чека</a>', url)
    receipt_preview.short_description = "Чек"

    @admin.action(description="Отметить оплачено (success)")
    def mark_success(self, request, queryset):
        updated = queryset.update(status="success")
        self.message_user(request, f"Обновлено {updated} платежей как 'success'.")
        # авто-зачисление
        for p in queryset.select_related("user", "course"):
            try:
                Enrollment.objects.get_or_create(user=p.user, course=p.course)
                p.course.students.add(p.user)
            except Exception:
                pass

    @admin.action(description="Отметить ошибку (failed)")
    def mark_failed(self, request, queryset):
        updated = queryset.update(status="failed")
        self.message_user(request, f"Обновлено {updated} платежей как 'failed'.")


# ---------------------------
# Subscription
# ---------------------------

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "start_date", "end_date", "active")
    list_filter = ("active", "start_date")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user",)
    ordering = ("-start_date",)
    list_select_related = ("user",)


# ---------------------------
# ContactMessage
# ---------------------------

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


# ---------------------------
# Site headers
# ---------------------------

admin.site.site_header = "🏔️ SkillsSpire — Панель управления"
admin.site.site_title = "SkillsSpire Admin"
admin.site.index_title = "Управление образовательной платформой SkillsSpire"
