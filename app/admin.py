from django.contrib import admin
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


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    fields = ("title", "order", "is_active")


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("title", "slug", "order", "is_active", "is_free")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "order")
    list_editable = ("is_active", "order")
    search_fields = ("name", "description")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_approved", "specialization", "experience", "courses_count", "created_at")
    list_filter = ("is_approved",)
    search_fields = ("user__username", "user__first_name", "user__last_name", "specialization")
    readonly_fields = ("courses_count", "created_at", "updated_at")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "instructor",
        "status",
        "level",
        "price",
        "is_featured",
        "is_popular",
        "created_at",
    )
    list_filter = ("category", "status", "level", "is_featured", "is_popular", "created_at")
    search_fields = ("title", "short_description", "description")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category", "instructor", "author", "students")
    readonly_fields = ("students_count", "reviews_count", "rating", "created_at", "updated_at")
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_active")
    list_filter = ("is_active", "course")
    search_fields = ("title", "description", "course__title")
    autocomplete_fields = ("course",)
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "order", "is_active", "is_free", "created_at")
    list_filter = ("is_active", "is_free", "module__course")
    search_fields = ("title", "content", "module__title", "module__course__title")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("module",)


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "lesson", "is_completed", "completed_at")
    list_filter = ("is_completed", "completed_at")
    search_fields = ("user__username", "lesson__title", "lesson__module__course__title")
    autocomplete_fields = ("user", "lesson")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "enrolled_at", "completed", "completed_at")
    list_filter = ("completed", "enrolled_at")
    search_fields = ("user__username", "course__title")
    autocomplete_fields = ("user", "course")


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
    list_display = ("user", "course", "amount", "status", "kaspi_invoice_id", "created", "updated")
    list_filter = ("status", "created")
    search_fields = ("user__username", "course__title", "kaspi_invoice_id")
    autocomplete_fields = ("user", "course")


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
