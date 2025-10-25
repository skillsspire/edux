from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.template.response import TemplateResponse
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

from .models import (
    Category, InstructorProfile, Course, Module, Lesson, LessonProgress,
    Enrollment, Review, Wishlist, Payment, ContactMessage, Article, Material,
)

IMAGE_PREVIEW_SIZE = {"width": 100, "height": 70}
DEFAULT_EMPTY_VALUE = "—"

class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    fields = ("title", "order", "is_active", "lesson_count")
    readonly_fields = ("lesson_count",)
    show_change_link = True
    
    def lesson_count(self, obj):
        return obj.lessons.count()

class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("title", "slug", "order", "is_active", "duration_minutes", "completion_rate")
    readonly_fields = ("completion_rate",)
    prepopulated_fields = {"slug": ("title",)}
    show_change_link = True
    
    def completion_rate(self, obj):
        total = LessonProgress.objects.filter(lesson=obj).count()
        completed = LessonProgress.objects.filter(lesson=obj, is_completed=True).count()
        return f"{round((completed/total*100), 1) if total else 0}%"

class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    readonly_fields = ("user", "completed", "created_at")
    can_delete = False

class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ("user", "rating", "comment", "created_at")
    can_delete = False

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("user", "amount", "status", "created_at")
    can_delete = False

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "courses_count", "student_count")
    list_editable = ("is_active",)
    search_fields = ("name",)
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}

    def courses_count(self, obj):
        return obj.courses.count()

    def student_count(self, obj):
        return User.objects.filter(enrolled_courses__category=obj).distinct().count()

@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "specialization", "courses_count", "students_count", "avg_rating", "is_approved")
    list_filter = ("is_approved", "created_at")
    search_fields = ("user__username", "user__email", "specialization")
    readonly_fields = ("created_at", "updated_at", "courses_count", "students_count", "avg_rating")
    actions = ["approve_instructors"]

    def courses_count(self, obj):
        return obj.user.taught_courses.count()

    def students_count(self, obj):
        return User.objects.filter(enrolled_courses__instructor=obj.user).distinct().count()

    def avg_rating(self, obj):
        avg = Review.objects.filter(course__instructor=obj.user).aggregate(Avg('rating'))['rating__avg']
        return round(avg, 2) if avg else 0

    @admin.action(description="Подтвердить выбранных инструкторов")
    def approve_instructors(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"Подтверждено {updated} инструкторов")

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
        "completion_rate",
        "revenue",
        "avg_rating",
        "created_at",
    )
    list_display_links = ("image_preview", "title")
    list_filter = ("category", "level", "is_featured", "created_at")
    search_fields = ("title", "short_description", "description", "category__name", "instructor__username")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category", "instructor")
    readonly_fields = ("created_at", "updated_at", "image_preview", "completion_rate", "revenue", "students_count", "avg_rating")
    inlines = [ModuleInline, EnrollmentInline, ReviewInline, PaymentInline]
    ordering = ("-created_at",)
    list_select_related = ("category", "instructor")
    actions = ["duplicate_courses", "toggle_featured"]

    fieldsets = (
        ("Основное", {
            "fields": ("title", "slug", "category", "instructor", "short_description", "description")
        }),
        ("Медиа", {
            "fields": ("image", "thumbnail", "image_preview")
        }),
        ("Настройки", {
            "fields": ("level", "duration_hours", "is_featured", "price", "discount_price")
        }),
        ("Статистика", {
            "fields": ("students_count", "completion_rate", "revenue", "avg_rating"),
            "classes": ("collapse",)
        }),
        ("Служебное", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def image_preview(self, obj):
        url = obj.display_image_url
        if url:
            return format_html(
                '<img src="{}" width="{}" height="{}" style="object-fit:cover;border-radius:6px;">',
                url, IMAGE_PREVIEW_SIZE["width"], IMAGE_PREVIEW_SIZE["height"]
            )
        return DEFAULT_EMPTY_VALUE

    def students_count(self, obj):
        return obj.students.count()

    def avg_rating(self, obj):
        try:
            return round(obj.reviews.aggregate(a=Avg("rating"))["a"] or 0, 2)
        except Exception:
            return 0

    def completion_rate(self, obj):
        total = obj.enrollments.count()
        completed = obj.enrollments.filter(completed=True).count()
        return f"{round((completed/total*100), 1) if total else 0}%"

    def revenue(self, obj):
        total = Payment.objects.filter(course=obj, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        return f"{total:,} ₸"

    @admin.action(description="Дублировать выбранные курсы")
    def duplicate_courses(self, request, queryset):
        for course in queryset:
            course.pk = None
            course.title = f"{course.title} (копия)"
            course.slug = f"{course.slug}-copy-{int(timezone.now().timestamp())}"
            course.save()
        self.message_user(request, f"Создано {queryset.count()} копий курсов")

    @admin.action(description="Переключить featured статус")
    def toggle_featured(self, request, queryset):
        for course in queryset:
            course.is_featured = not course.is_featured
            course.save()
        self.message_user(request, f"Обновлено {queryset.count()} курсов")

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_active", "lessons_count", "completion_rate")
    list_filter = ("is_active", "course")
    search_fields = ("title", "course__title")
    autocomplete_fields = ("course",)
    inlines = [LessonInline]
    ordering = ("course", "order")
    list_select_related = ("course",)
    readonly_fields = ("completion_rate",)

    def lessons_count(self, obj):
        return obj.lessons.count()

    def completion_rate(self, obj):
        progresses = LessonProgress.objects.filter(lesson__module=obj)
        total = progresses.count()
        completed = progresses.filter(is_completed=True).count()
        return f"{round((completed/total*100), 1) if total else 0}%"

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "course_display", "order", "is_active", "duration_minutes", "completion_rate")
    list_filter = ("is_active", "module__course")
    search_fields = ("title", "module__title", "module__course__title")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("module",)
    ordering = ("module__course", "module__order", "order")
    list_select_related = ("module", "module__course")
    readonly_fields = ("completion_rate",)

    def course_display(self, obj):
        return obj.module.course.title if obj.module and obj.module.course else DEFAULT_EMPTY_VALUE

    def completion_rate(self, obj):
        total = LessonProgress.objects.filter(lesson=obj).count()
        completed = LessonProgress.objects.filter(lesson=obj, is_completed=True).count()
        return f"{round((completed/total*100), 1) if total else 0}%"

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "lesson", "course_display", "is_completed", "percent", "updated_at")
    list_filter = ("is_completed", "updated_at", "lesson__module__course")
    search_fields = ("user__username", "user__email", "lesson__title", "lesson__module__course__title")
    autocomplete_fields = ("user", "lesson")
    readonly_fields = ("updated_at", "course_display")
    ordering = ("-updated_at",)
    list_select_related = ("lesson", "lesson__module", "lesson__module__course", "user")

    def course_display(self, obj):
        return obj.lesson.module.course.title if obj.lesson.module else DEFAULT_EMPTY_VALUE

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "completed", "progress_percentage", "created_at", "last_activity")
    list_filter = ("completed", "created_at", "course")
    search_fields = ("user__username", "user__email", "course__title")
    autocomplete_fields = ("user", "course")
    readonly_fields = ("created_at", "progress_percentage", "last_activity")
    ordering = ("-created_at",)
    list_select_related = ("user", "course")
    actions = ["mark_completed", "mark_incomplete"]

    def progress_percentage(self, obj):
        total_lessons = obj.course.lessons.count()
        if total_lessons == 0:
            return "0%"
        completed_lessons = LessonProgress.objects.filter(
            user=obj.user, 
            lesson__module__course=obj.course, 
            is_completed=True
        ).count()
        return f"{round((completed_lessons/total_lessons*100), 1)}%"

    def last_activity(self, obj):
        last_progress = LessonProgress.objects.filter(
            user=obj.user, 
            lesson__module__course=obj.course
        ).order_by('-updated_at').first()
        return last_progress.updated_at if last_progress else DEFAULT_EMPTY_VALUE

    @admin.action(description="Отметить как завершённые")
    def mark_completed(self, request, queryset):
        updated = queryset.update(completed=True)
        self.message_user(request, f"Отмечено {updated} записей как завершённые")

    @admin.action(description="Отметить как незавершённые")
    def mark_incomplete(self, request, queryset):
        updated = queryset.update(completed=False)
        self.message_user(request, f"Отмечено {updated} записей как незавершённые")

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "rating", "is_active", "created_at", "comment_preview")
    list_filter = ("rating", "is_active", "created_at", "course")
    search_fields = ("user__username", "user__email", "course__title", "comment")
    autocomplete_fields = ("user", "course")
    ordering = ("-created_at",)
    list_select_related = ("user", "course")
    actions = ["activate_reviews", "deactivate_reviews"]

    def comment_preview(self, obj):
        return obj.comment[:100] + "..." if len(obj.comment) > 100 else obj.comment

    @admin.action(description="Активировать отзывы")
    def activate_reviews(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Активировано {updated} отзывов")

    @admin.action(description="Деактивировать отзывы")
    def deactivate_reviews(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано {updated} отзывов")

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "created_at")
    list_filter = ("created_at", "course")
    search_fields = ("user__username", "user__email", "course__title")
    autocomplete_fields = ("user", "course")
    ordering = ("-created_at",)
    list_select_related = ("user", "course")

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "amount", "status", "type", "kaspi_invoice_id", "created_at", "revenue_impact")
    list_filter = ("status", "type", "created_at", "course")
    search_fields = ("user__username", "user__email", "course__title", "kaspi_invoice_id")
    autocomplete_fields = ("user", "course")
    ordering = ("-created_at",)
    list_select_related = ("user", "course")
    readonly_fields = ("created_at", "updated_at", "receipt_preview", "revenue_impact")
    actions = ("mark_success", "mark_failed", "export_payments")

    fieldsets = (
        ("Основное", {"fields": ("user", "course", "amount", "status", "type")}),
        ("Kaspi", {"fields": ("kaspi_invoice_id",)}),
        ("Чек", {"fields": ("receipt", "receipt_preview")}),
        ("Служебное", {"fields": ("created_at", "updated_at", "revenue_impact")}),
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

    def revenue_impact(self, obj):
        if obj.status == 'success':
            return format_html('<span style="color: green;">+{} ₸</span>', obj.amount)
        return format_html('<span style="color: red;">0 ₸</span>')

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

    @admin.action(description="Экспорт платежей в CSV")
    def export_payments(self, request, queryset):
        pass

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "is_processed", "created_at", "message_preview")
    list_filter = ("created_at", "is_processed")
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    actions = ["mark_as_processed", "mark_as_unprocessed"]

    def message_preview(self, obj):
        return obj.message[:100] + "..." if len(obj.message) > 100 else obj.message

    @admin.action(description="Отметить как обработанное")
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(is_processed=True)
        self.message_user(request, f"Отмечено {updated} сообщений как обработанные")

    @admin.action(description="Отметить как необработанное")
    def mark_as_unprocessed(self, request, queryset):
        updated = queryset.update(is_processed=False)
        self.message_user(request, f"Отмечено {updated} сообщений как необработанные")

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("cover_preview", "title", "status", "published_at", "view_count", "created_at")
    list_filter = ("status", "published_at", "created_at")
    search_fields = ("title", "excerpt", "body", "seo_title", "seo_description", "seo_keywords")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at", "cover_preview", "view_count")
    date_hierarchy = "published_at"
    ordering = ("-published_at", "-created_at")
    actions = ["publish_articles", "unpublish_articles"]

    fieldsets = (
        ("Основное", {"fields": ("title", "slug", "excerpt", "cover", "cover_preview", "body", "status", "published_at", "view_count")}),
        ("SEO", {"fields": ("seo_title", "seo_description", "seo_keywords", "seo_schema")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )

    def cover_preview(self, obj):
        if obj.cover and hasattr(obj.cover, "url"):
            return format_html('<img src="{}" style="max-width:160px; max-height:100px; object-fit:cover; border-radius:6px;">', obj.cover.url)
        return "—"

    @admin.action(description="Опубликовать статьи")
    def publish_articles(self, request, queryset):
        updated = queryset.update(status="published", published_at=timezone.now())
        self.message_user(request, f"Опубликовано {updated} статей")

    @admin.action(description="Снять с публикации")
    def unpublish_articles(self, request, queryset):
        updated = queryset.update(status="draft")
        self.message_user(request, f"Снято с публикации {updated} статей")

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "file_preview", "is_public", "download_count", "created_at")
    list_filter = ("is_public", "created_at")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at", "download_count", "file_preview")
    ordering = ("-created_at",)
    actions = ["make_public", "make_private"]

    def file_preview(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">📎 {}</a>', obj.file.url, obj.file.name.split('/')[-1])
        return "—"

    @admin.action(description="Сделать публичными")
    def make_public(self, request, queryset):
        updated = queryset.update(is_public=True)
        self.message_user(request, f"Сделано публичными {updated} материалов")

    @admin.action(description="Сделать приватными")
    def make_private(self, request, queryset):
        updated = queryset.update(is_public=False)
        self.message_user(request, f"Сделано приватными {updated} материалов")

class CustomAdminSite(admin.AdminSite):
    site_header = "🎯 SkillsSpire Platform — Единый центр управления"
    site_title = "SkillsSpire Platform"
    index_title = "Панель управления образовательной платформой"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('platform-dashboard/', self.admin_view(self.platform_dashboard), name='platform-dashboard'),
            path('learning-analytics/', self.admin_view(self.learning_analytics), name='learning-analytics'),
            path('financial-reports/', self.admin_view(self.financial_reports), name='financial-reports'),
        ]
        return custom_urls + urls
    
    def platform_dashboard(self, request):
        week_ago = timezone.now() - timedelta(days=7)
        month_ago = timezone.now() - timedelta(days=30)
        
        total_students = Course.objects.aggregate(
            total=Count('students', distinct=True)
        )['total'] or 0
        
        total_revenue = Payment.objects.filter(
            status='success', 
            created_at__gte=month_ago
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        active_learners = Enrollment.objects.filter(
            created_at__gte=week_ago
        ).count()
        
        completion_rate = self.calculate_completion_rate()
        
        popular_courses = Course.objects.annotate(
            enrollment_count=Count('enrollments')
        ).order_by('-enrollment_count')[:5]
        
        recent_payments = Payment.objects.select_related('user', 'course').filter(
            status='success'
        ).order_by('-created_at')[:10]

        context = {
            **self.each_context(request),
            'total_students': total_students,
            'total_courses': Course.objects.count(),
            'total_revenue': total_revenue,
            'active_learners': active_learners,
            'completion_rate': completion_rate,
            'popular_courses': popular_courses,
            'recent_payments': recent_payments,
            'pending_messages': ContactMessage.objects.filter(is_processed=False)[:5],
            'recent_enrollments': Enrollment.objects.select_related('user', 'course').order_by('-created_at')[:5],
        }
        return TemplateResponse(request, "admin/platform_dashboard.html", context)
    
    def learning_analytics(self, request):
        course_progress = Course.objects.annotate(
            total_enrollments=Count('enrollments'),
            completed_enrollments=Count('enrollments', filter=Q(enrollments__completed=True)),
            avg_rating=Avg('reviews__rating')
        ).order_by('-total_enrollments')
        
        context = {
            **self.each_context(request),
            'course_progress': course_progress,
        }
        return TemplateResponse(request, "admin/learning_analytics.html", context)
    
    def financial_reports(self, request):
        monthly_revenue = Payment.objects.filter(
            status='success',
            created_at__gte=timezone.now() - timedelta(days=365)
        ).extra({
            'month': "strftime('%%Y-%%m', created_at)"
        }).values('month').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('month')
        
        context = {
            **self.each_context(request),
            'monthly_revenue': monthly_revenue,
        }
        return TemplateResponse(request, "admin/financial_reports.html", context)
    
    def calculate_completion_rate(self):
        total_enrollments = Enrollment.objects.count()
        completed_enrollments = Enrollment.objects.filter(completed=True).count()
        return round((completed_enrollments / total_enrollments * 100), 2) if total_enrollments else 0

    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        
        custom_app_list = []
        
        learning_app = {
            'name': '🏫 Обучение',
            'app_label': 'learning',
            'models': []
        }
        
        sales_app = {
            'name': '💼 Продажи и CRM',
            'app_label': 'sales',
            'models': []
        }
        
        content_app = {
            'name': '🧠 Контент',
            'app_label': 'content',
            'models': []
        }
        
        for app in app_list:
            if app['app_label'] == 'app':
                for model in app['models']:
                    if model['object_name'] in ['Course', 'Module', 'Lesson', 'LessonProgress', 'Enrollment']:
                        learning_app['models'].append(model)
                    elif model['object_name'] in ['Payment', 'Review', 'Wishlist', 'ContactMessage']:
                        sales_app['models'].append(model)
                    elif model['object_name'] in ['Category', 'Article', 'Material']:
                        content_app['models'].append(model)
                    elif model['object_name'] in ['InstructorProfile']:
                        learning_app['models'].append(model)
        
        custom_app_list.extend([learning_app, sales_app, content_app])
        return custom_app_list

admin_site = CustomAdminSite(name='skills_spire_admin')

admin_site.register(Category, CategoryAdmin)
admin_site.register(InstructorProfile, InstructorProfileAdmin)
admin_site.register(Course, CourseAdmin)
admin_site.register(Module, ModuleAdmin)
admin_site.register(Lesson, LessonAdmin)
admin_site.register(LessonProgress, LessonProgressAdmin)
admin_site.register(Enrollment, EnrollmentAdmin)
admin_site.register(Review, ReviewAdmin)
admin_site.register(Wishlist, WishlistAdmin)
admin_site.register(Payment, PaymentAdmin)
admin_site.register(ContactMessage, ContactMessageAdmin)
admin_site.register(Article, ArticleAdmin)
admin_site.register(Material, MaterialAdmin)

admin.site = admin_site