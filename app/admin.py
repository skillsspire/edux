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
    ContactMessage,
    Article,
    Material,
)

IMAGE_PREVIEW_SIZE = {"width": 100, "height": 70}
DEFAULT_EMPTY_VALUE = "—"


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    fields = ("title", "order", "is_active")
    show_change_link = True


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("title", "slug", "order", "is_active", "duration_minutes")
    prepopulated_fields = {"slug": ("title",)}
    show_change_link = True


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "courses_count")
    list_editable = ("is_active",)
    search_fields = ("name",)
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}

    def courses_count(self, obj):
        return obj.courses.count()
    courses_count.short_description = "Курсов"


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "specialization", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("user__username", "user__email", "specialization")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "image_preview",
        "title",
        "category",
        "instructor",
        "price",
        "discount_price",
        "level",
        "is_featured",
        "students_count",
        "avg_rating",
        "created_at",
    )
    list_display_links = ("image_preview", "title")
    list_filter = ("category", "level", "is_featured", "created_at")
    search_fields = ("title", "short_description", "description", "category__name", "instructor__username")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category", "instructor")
    readonly_fields = ("created_at", "updated_at", "image_preview")
    inlines = [ModuleInline]
    ordering = ("-created_at",)
    list_select_related = ("category", "instructor")

    def image_preview(self, obj):
        url = getattr(obj, "display_image_url", None) or (
            obj.image.url if getattr(obj, "image", None) and hasattr(obj.image, "url") else None
        )
        if url:
            return format_html(
                '<img src="{}" width="{}" height="{}" style="object-fit:cover;border-radius:6px;">',
                url, IMAGE_PREVIEW_SIZE["width"], IMAGE_PREVIEW_SIZE["height"]
            )
        return DEFAULT_EMPTY_VALUE
    image_preview.short_description = "Превью"

    def students_count(self, obj):
        return obj.students.count()
    students_count.short_description = "Студентов"

    def avg_rating(self, obj):
        try:
            from django.db.models import Avg
            return round(obj.reviews.aggregate(a=Avg("rating"))["a"] or 0, 2)
        except Exception:
            return 0
    avg_rating.short_description = "Рейтинг"


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_active")
    list_filter = ("is_active", "course")
    search_fields = ("title", "course__title")
    autocomplete_fields = ("course",)
    inlines = [LessonInline]
    ordering = ("course", "order")
    list_select_related = ("course",)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "course_display", "order", "is_active", "duration_minutes")
    list_filter = ("is_active", "module__course")
    search_fields = ("title", "module__title", "module__course__title")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("module",)
    ordering = ("module__course", "module__order", "order")
    list_select_related = ("module", "module__course")

    def course_display(self, obj):
        return obj.module.course.title if obj.module and obj.module.course else DEFAULT_EMPTY_VALUE
    course_display.short_description = "Курс"


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "lesson", "is_completed", "percent", "updated_at")
    list_filter = ("is_completed", "updated_at")
    search_fields = ("user__username", "user__email", "lesson__title", "lesson__module__course__title")
    autocomplete_fields = ("user", "lesson")
    readonly_fields = ("updated_at",)
    ordering = ("-updated_at",)
    list_select_related = ("lesson", "lesson__module", "lesson__module__course", "user")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "completed", "created_at")
    list_filter = ("completed", "created_at")
    search_fields = ("user__username", "user__email", "course__title")
    autocomplete_fields = ("user", "course")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    list_select_related = ("user", "course")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "rating", "is_active", "created_at")
    list_filter = ("rating", "is_active", "created_at")
    search_fields = ("user__username", "user__email", "course__title", "comment")
    autocomplete_fields = ("user", "course")
    ordering = ("-created_at",)
    list_select_related = ("user", "course")


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "user__email", "course__title")
    autocomplete_fields = ("user", "course")
    ordering = ("-created_at",)
    list_select_related = ("user", "course")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "amount", "status", "kaspi_invoice_id", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "user__email", "course__title", "kaspi_invoice_id")
    autocomplete_fields = ("user", "course")
    ordering = ("-created_at",)
    list_select_related = ("user", "course")
    readonly_fields = ("created_at", "updated_at", "receipt_preview")

    actions = ("mark_success", "mark_failed")

    fieldsets = (
        (None, {"fields": ("user", "course", "amount", "status")}),
        ("Kaspi", {"fields": ("kaspi_invoice_id",)}),
        ("Чек", {"fields": ("receipt", "receipt_preview")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )

    def receipt_preview(self, obj):
        f = getattr(obj, "receipt", None)
        if not f:
            return DEFAULT_EMPTY_VALUE
        url = getattr(f, "url", "") or getattr(f, "name", "")
        if not url:
            return DEFAULT_EMPTY_VALUE
        lower = str(url).lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return format_html('<img src="{}" style="max-width:280px;max-height:180px;object-fit:contain;border-radius:6px;">', url)
        return format_html('<a href="{}" target="_blank" rel="noopener">Открыть файл чека</a>', url)
    receipt_preview.short_description = "Чек"

    @admin.action(description="Отметить оплачено (success)")
    def mark_success(self, request, queryset):
        updated = queryset.update(status="success")
        self.message_user(request, f"Обновлено {updated} платежей как 'success'.")
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


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "published_at", "created_at")
    list_filter = ("status", "published_at", "created_at")
    search_fields = ("title", "excerpt", "body", "seo_title", "seo_description", "seo_keywords")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "published_at"
    ordering = ("-published_at", "-created_at")
    fieldsets = (
        (None, {"fields": ("title", "slug", "excerpt", "cover", "body", "status", "published_at")}),
        ("SEO", {"fields": ("seo_title", "seo_description", "seo_keywords", "seo_schema")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "is_public", "created_at")
    list_filter = ("is_public", "created_at")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


admin.site.site_header = "🏔️ SkillsSpire — Панель управления"
admin.site.site_title = "SkillsSpire Admin"
admin.site.index_title = "Управление образовательной платформой SkillsSpire"
