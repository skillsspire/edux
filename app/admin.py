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

IMAGE_PREVIEW_SIZE = {"width": 100, "height": 70}
VIDEO_PREVIEW_SIZE = {"width": 180, "height": 100}
DEFAULT_EMPTY_VALUE = "—"


class SafeFieldMixin:
    def _first_attr(self, obj, *names, default=DEFAULT_EMPTY_VALUE):
        for name in names:
            if hasattr(obj, name):
                val = getattr(obj, name)
                if val:
                    return str(val)
        return default


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


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "specialization", "experience", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("user__username", "specialization")
    readonly_fields = ("created_at", "updated_at")


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
    search_fields = ("title", "short_description", "description")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category", "instructor", "students")
    readonly_fields = ("students_count", "reviews_count", "rating", "created_at", "updated_at", "image_preview")
    inlines = [ModuleInline]
    ordering = ("-created_at",)

    def image_preview(self, obj):
        if obj.image and hasattr(obj.image, "url"):
            return format_html(
                '<img src="{}" width="{}" height="{}" style="object-fit:cover;border-radius:6px;">',
                obj.image.url, IMAGE_PREVIEW_SIZE["width"], IMAGE_PREVIEW_SIZE["height"]
            )
        return DEFAULT_EMPTY_VALUE
    image_preview.short_description = "Превью"


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_active")
    list_filter = ("is_active", "course")
    search_fields = ("title", "description", "course__title")
    autocomplete_fields = ("course",)
    inlines = [LessonInline]
    ordering = ("course", "order")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "course_display", "order", "is_active", "is_free", "video_preview")
    list_filter = ("is_active", "is_free", "module__course")
    search_fields = ("title", "content", "module__title", "module__course__title")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("module",)
    readonly_fields = ("video_preview",)
    ordering = ("module__course", "module__order", "order")

    def course_display(self, obj):
        return obj.module.course.title if obj.module and obj.module.course else DEFAULT_EMPTY_VALUE
    course_display.short_description = "Курс"

    def video_preview(self, obj):
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


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "lesson", "is_completed", "updated_at")
    list_filter = ("is_completed", "updated_at")
    search_fields = ("user__username", "lesson__title", "lesson__module__course__title")
    autocomplete_fields = ("user", "lesson")
    readonly_fields = ("updated_at",)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "enrolled_at", "completed", "completed_at")
    list_filter = ("completed", "enrolled_at")
    search_fields = ("user__username", "course__title")
    autocomplete_fields = ("user", "course")
    readonly_fields = ("enrolled_at",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "rating", "is_active", "created_at")
    list_filter = ("rating", "is_active", "created_at")
    search_fields = ("user__username", "course__title", "comment")
    autocomplete_fields = ("user", "course")


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "added_at")
    list_filter = ("added_at",)
    search_fields = ("user__username", "course__title")
    autocomplete_fields = ("user", "course")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "amount", "status", "created")
    list_filter = ("status", "created")
    search_fields = ("user__username", "course__title")
    autocomplete_fields = ("user", "course")
    readonly_fields = ("created", "updated")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "start_date", "end_date", "active")
    list_filter = ("active", "start_date")
    search_fields = ("user__username",)
    autocomplete_fields = ("user",)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("created_at",)


admin.site.site_header = "🏔️ SkillsSpire — Панель управления"
admin.site.site_title = "SkillsSpire Admin"
admin.site.index_title = "Управление образовательной платформой SkillsSpire"
