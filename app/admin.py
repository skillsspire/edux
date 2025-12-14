from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta

from .models import (
    Category,
    Course,
    Enrollment,
    InstructorProfile,
    Lesson,
    BlockProgress,
    Payment,
    Review,
    Wishlist,
    Article,
    Material,
    UserProfile,
    Module,
    LessonBlock,
    Quiz, Question, Answer, Assignment, Submission, Certificate,
    Lead, Interaction, Segment, SupportTicket, FAQ,
    Plan, Subscription, Refund, Mailing,
    CourseStaff, AuditLog,
    ContactMessage
)

# 🔥 СТАНДАРТНЫЕ МОДЕЛИ DJANGO
admin.site.unregister(User)
admin.site.unregister(Group)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'full_name', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}" if obj.first_name or obj.last_name else "—"

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    filter_horizontal = ['permissions']

# 🏗️ ЯДРО ПЛАТФОРМЫ
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'course_count', 'is_active']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'slug']  # ← ДОБАВЛЕНО
    
    def course_count(self, obj):
        return obj.courses.count()

class CourseStaffInline(admin.TabularInline):
    model = CourseStaff
    extra = 1
    autocomplete_fields = ['user']

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'category', 'instructor', 'price_display', 'students_count', 'revenue', 'created_at']
    list_filter = ['status', 'category', 'level', 'is_featured', 'created_at']
    search_fields = ['title', 'description', 'instructor__username']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'updated_at', 'students_count', 'revenue', 'completion_rate']
    autocomplete_fields = ['category', 'instructor']
    ordering = ['-created_at']
    inlines = [CourseStaffInline]
    
    fieldsets = (
        ('Основное', {'fields': ('title', 'slug', 'status', 'category', 'instructor')}),
        ('Контент', {'fields': ('short_description', 'description', 'image', 'thumbnail')}),
        ('Настройки', {'fields': ('level', 'duration_hours', 'is_featured', 'price', 'discount_price', 'certificate')}),
        ('Требования', {'fields': ('requirements', 'what_you_learn'), 'classes': ('collapse',)}),
        ('Статистика', {'fields': ('students_count', 'completion_rate', 'revenue'), 'classes': ('collapse',)}),
        ('Служебное', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def price_display(self, obj):
        if obj.discount_price and obj.discount_price < obj.price:
            return format_html(
                '<span style="text-decoration: line-through;">{}</span> <span style="color: #dc2626;">{}</span>',
                f"{obj.price:,} ₸",
                f"{obj.discount_price:,} ₸"
            )
        return f"{obj.price:,} ₸"
    
    def students_count(self, obj):
        return obj.enrollments.count()
    
    def revenue(self, obj):
        total = Payment.objects.filter(course=obj, status='success').aggregate(Sum('amount'))['amount__sum'] or 0
        return f"{total:,} ₸"
    
    def completion_rate(self, obj):
        total = obj.enrollments.count()
        completed = obj.enrollments.filter(completed=True).count()
        return f"{round((completed/total*100), 1) if total else 0}%"

class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1
    fields = ['title', 'slug', 'order', 'duration_minutes', 'is_active', 'is_free']
    prepopulated_fields = {'slug': ('title',)}

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order', 'lesson_count', 'is_active']
    list_filter = ['course', 'is_active']
    inlines = [LessonInline]
    ordering = ['course', 'order']
    
    def lesson_count(self, obj):
        return obj.lessons.count()

class LessonBlockInline(admin.TabularInline):
    model = LessonBlock
    extra = 1
    fields = ['block_type', 'title', 'order', 'is_required', 'is_free_preview']

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'module', 'course_name', 'order', 'duration_minutes', 'is_active', 'block_count']
    list_filter = ['module__course', 'is_active', 'is_free']
    search_fields = ['title', 'module__course__title']
    prepopulated_fields = {'slug': ('title',)}
    ordering = ['module__course', 'module__order', 'order']
    inlines = [LessonBlockInline]
    
    def course_name(self, obj):
        return obj.module.course.title if obj.module else "—"
    
    def block_count(self, obj):
        return obj.blocks.count()

# 💰 ФИНАНСЫ (только для superusers)
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'amount', 'status', 'type', 'created_at', 'revenue_impact']
    list_filter = ['status', 'type', 'created_at']
    search_fields = ['user__username', 'course__title', 'kaspi_invoice_id', 'payment_id']
    readonly_fields = ['created_at', 'updated_at', 'payment_id', 'idempotency_key']
    ordering = ['-created_at']
    
    def revenue_impact(self, obj):
        if obj.status == 'success':
            return format_html('<span style="color: #059669; font-weight: bold;">+{} ₸</span>', f"{obj.amount:,}")
        return format_html('<span style="color: #dc2626;">—</span>')

# 📊 ОБУЧЕНИЕ (LMS)
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'completed', 'progress', 'created_at']
    list_filter = ['completed', 'course', 'created_at']
    search_fields = ['user__username', 'course__title']
    readonly_fields = ['created_at', 'progress']
    
    def progress(self, obj):
        # Теперь считаем прогресс по блокам, а не по урокам
        total_blocks = LessonBlock.objects.filter(
            lesson__module__course=obj.course,
            is_required=True,
            is_deleted=False
        ).count()
        
        if total_blocks == 0:
            return "0%"
            
        completed_blocks = BlockProgress.objects.filter(
            user=obj.user,
            block__lesson__module__course=obj.course,
            is_completed=True
        ).count()
        
        return f"{round((completed_blocks/total_blocks*100), 1)}%"

@admin.register(BlockProgress)
class BlockProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'block', 'progress_percent', 'is_completed', 'time_spent', 'last_accessed']
    list_filter = ['is_completed', 'created_at']
    search_fields = ['user__username', 'block__title']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['user', 'block']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['course', 'user', 'rating', 'is_active', 'created_at', 'comment_preview']
    list_filter = ['rating', 'is_active', 'course']
    search_fields = ['course__title', 'user__username', 'comment']
    list_editable = ['is_active']
    
    def comment_preview(self, obj):
        return obj.comment[:100] + "..." if len(obj.comment) > 100 else obj.comment

# 🎯 CRM (модерация)
@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'source', 'status', 'converted', 'created_at']
    list_filter = ['status', 'source', 'converted']
    search_fields = ['email', 'name', 'phone']
    list_editable = ['status']

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'subject', 'is_processed', 'created_at']
    list_filter = ['is_processed', 'created_at']
    search_fields = ['email', 'name', 'subject']
    list_editable = ['is_processed']

# 📝 КОНТЕНТ
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'published_at', 'view_count', 'created_at']
    list_filter = ['status', 'published_at']
    search_fields = ['title', 'excerpt']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    
    fieldsets = (
        ('Основное', {'fields': ('title', 'slug', 'status', 'published_at', 'author')}),
        ('Контент', {'fields': ('excerpt', 'body', 'cover')}),
        ('SEO', {'fields': ('seo_title', 'seo_description', 'seo_keywords')}),
    )

# 🔥 КАСТОМНЫЕ ДЕЙСТВИЯ
@admin.action(description="✅ Опубликовать выбранные курсы")
def make_published(modeladmin, request, queryset):
    for course in queryset:
        course.publish()
    modeladmin.message_user(request, f"{queryset.count()} курсов опубликовано")

@admin.action(description="📝 Перевести в черновик")
def make_draft(modeladmin, request, queryset):
    queryset.update(status='draft')
    modeladmin.message_user(request, f"{queryset.count()} курсов переведено в черновик")

@admin.action(description="📤 Отправить на проверку")
def submit_for_review(modeladmin, request, queryset):
    for course in queryset:
        course.submit_for_review()
    modeladmin.message_user(request, f"{queryset.count()} курсов отправлено на проверку")

@admin.action(description="✅ Одобрить курсы")
def approve_courses(modeladmin, request, queryset):
    for course in queryset:
        course.approve()
    modeladmin.message_user(request, f"{queryset.count()} курсов одобрено")

@admin.action(description="💰 Добавить скидку 20%")
def add_discount(modeladmin, request, queryset):
    for course in queryset:
        if course.price > 0:
            course.discount_price = course.price * 0.8
            course.save()
    modeladmin.message_user(request, f"Скидка 20% добавлена к {queryset.count()} курсам")

@admin.action(description="🗑️ Мягкое удаление")
def soft_delete(modeladmin, request, queryset):
    for obj in queryset:
        if hasattr(obj, 'soft_delete'):
            obj.soft_delete()
    modeladmin.message_user(request, f"{queryset.count()} объектов помечено как удалённые")

@admin.action(description="↩️ Восстановить удалённые")
def restore_deleted(modeladmin, request, queryset):
    for obj in queryset:
        if hasattr(obj, 'is_deleted'):
            obj.is_deleted = False
            obj.deleted_at = None
            obj.save()
    modeladmin.message_user(request, f"{queryset.count()} объектов восстановлено")

# Добавляем действия к CourseAdmin
CourseAdmin.actions = [make_published, make_draft, submit_for_review, approve_courses, add_discount, soft_delete, restore_deleted]

# Регистрируем LessonBlock с действиями
@admin.register(LessonBlock)
class LessonBlockAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'block_type', 'order', 'is_required', 'is_free_preview']
    list_filter = ['block_type', 'is_required', 'is_free_preview', 'is_deleted']
    search_fields = ['title', 'lesson__title']
    ordering = ['lesson', 'order']
    actions = [soft_delete, restore_deleted]

# 🏃‍♀️ БЫСТРАЯ РЕГИСТРАЦИЯ ОСТАЛЬНЫХ МОДЕЛЕЙ (без кастомизации)
# Сначала создаем простые классы с действиями для моделей с soft delete
@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialization', 'is_approved', 'created_at']
    search_fields = ['user__username', 'specialization']
    actions = [soft_delete, restore_deleted]

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform_role', 'city', 'balance', 'is_deleted']
    list_filter = ['platform_role', 'is_deleted']
    search_fields = ['user__username', 'phone', 'city']
    actions = [soft_delete, restore_deleted]

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'created_at']
    search_fields = ['user__username', 'course__title']
    actions = [soft_delete, restore_deleted]

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'download_count', 'is_public', 'created_at']
    search_fields = ['title', 'category']
    actions = [soft_delete, restore_deleted]

# Регистрируем остальные модели без кастомизации, но с действиями
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'user', 'object_type', 'object_id', 'created_at']
    list_filter = ['action', 'object_type', 'created_at']
    search_fields = ['user__username', 'object_id']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(CourseStaff)
class CourseStaffAdmin(admin.ModelAdmin):
    list_display = ['course', 'user', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'joined_at']
    search_fields = ['course__title', 'user__username']
    raw_id_fields = ['course', 'user']

# 📋 МОДЕЛИ БЕЗ КАСТОМИЗАЦИИ
@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'passing_score', 'time_limit', 'is_active']
    list_filter = ['is_active', 'lesson__module__course']
    search_fields = ['title', 'lesson__title']
    ordering = ['lesson', 'title']

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 3

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['text', 'quiz', 'question_type', 'order', 'points']
    list_filter = ['question_type', 'quiz']
    search_fields = ['text', 'quiz__title']
    inlines = [AnswerInline]
    ordering = ['quiz', 'order']

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['text', 'question', 'is_correct', 'order']
    list_filter = ['is_correct', 'question__quiz']
    search_fields = ['text', 'question__text']
    ordering = ['question', 'order']

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'due_date', 'max_points', 'is_active']
    list_filter = ['is_active', 'course', 'due_date']
    search_fields = ['title', 'course__title', 'description']
    date_hierarchy = 'due_date'

from django.contrib.admin import SimpleListFilter

class IsGradedFilter(SimpleListFilter):
    title = 'Оценено'
    parameter_name = 'is_graded'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Да'),
            ('no', 'Нет'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(grade__isnull=False)
        if self.value() == 'no':
            return queryset.filter(grade__isnull=True)
        return queryset

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['assignment', 'user', 'submitted_at', 'is_graded', 'grade']
    list_filter = [IsGradedFilter, 'assignment__course', 'submitted_at']  # ← Использование кастомного фильтра
    search_fields = ['user__username', 'assignment__title', 'text']
    readonly_fields = ['submitted_at']
    date_hierarchy = 'submitted_at'
    
    def is_graded(self, obj):
        return obj.grade is not None
    is_graded.boolean = True
    is_graded.short_description = 'Оценено'

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'certificate_id', 'issued_at', 'is_revoked']
    list_filter = ['is_revoked', 'course', 'issued_at']
    search_fields = ['user__username', 'course__title', 'certificate_id']
    readonly_fields = ['certificate_id', 'issued_at']

@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ['lead', 'type', 'created_by', 'follow_up_date', 'is_completed']
    list_filter = ['type', 'is_completed', 'created_at']
    search_fields = ['lead__email', 'lead__name', 'description']
    date_hierarchy = 'created_at'

@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'is_dynamic', 'user_count']
    list_filter = ['is_active', 'is_dynamic']
    search_fields = ['name', 'description']
    filter_horizontal = ['users']

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['user', 'ticket_id', 'subject', 'status', 'priority', 'created_at']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['user__username', 'subject', 'ticket_id', 'description']
    readonly_fields = ['ticket_id']
    date_hierarchy = 'created_at'

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'order', 'is_active', 'view_count']
    list_filter = ['category', 'is_active']
    search_fields = ['question', 'answer']
    ordering = ['category', 'order']

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'duration_days', 'is_active', 'is_popular']
    list_filter = ['is_active', 'is_popular']
    search_fields = ['name', 'description']
    list_editable = ['is_active', 'is_popular']

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'start_date', 'end_date', 'is_active']
    list_filter = ['status', 'plan', 'start_date', 'end_date']
    search_fields = ['user__username', 'plan__name']
    readonly_fields = ['start_date', 'end_date']
    date_hierarchy = 'start_date'
    
    def is_active(self, obj):
        return obj.status == 'active' and obj.end_date > timezone.now()
    is_active.boolean = True

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['payment', 'user', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'payment__payment_id', 'reason']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    list_display = ['subject', 'channel', 'status', 'scheduled_for', 'sent_at', 'sent']
    list_filter = ['channel', 'status', 'scheduled_for']
    search_fields = ['subject', 'message']
    readonly_fields = ['sent', 'opens', 'clicks', 'unsubscribes', 'sent_at']
    date_hierarchy = 'created_at'

# 📊 Добавляем действия мягкого удаления к уже зарегистрированным моделям, у которых есть is_deleted
def add_actions_to_existing_models():
    """Добавляет действия к уже зарегистрированным моделям"""
    models_with_is_deleted = [
        Module, Lesson, Enrollment, Review, Article, Payment,
        Category, Course, ContactMessage, Lead
    ]
    
    for model in models_with_is_deleted:
        try:
            # Получаем админ-класс из реестра
            model_admin_instance = admin.site._registry[model]
            
            # Создаем новый список действий
            current_actions = list(getattr(model_admin_instance, 'actions', []))
            
            # Добавляем действия если их еще нет
            if soft_delete not in current_actions:
                current_actions.append(soft_delete)
            if restore_deleted not in current_actions:
                current_actions.append(restore_deleted)
            
            # Обновляем действия
            model_admin_instance.actions = current_actions
        except KeyError:
            # Модель не зарегистрирована, это нормально
            pass

# Вызываем функцию для добавления действий
add_actions_to_existing_models()