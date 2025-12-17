from decimal import Decimal
import logging
from typing import Optional
import uuid

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError, PermissionDenied

logger = logging.getLogger(__name__)


class TimestampedModel(models.Model):
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        abstract = True


class Category(TimestampedModel):
    name = models.CharField("Название", max_length=150, unique=True)
    slug = models.SlugField("Слаг", max_length=160, unique=True, blank=True)
    is_active = models.BooleanField("Активна", default=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:155]
        super().save(*args, **kwargs)


class UserProfile(TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="profile"
    )
    phone = models.CharField("Телефон", max_length=20, blank=True)
    city = models.CharField("Город", max_length=100, blank=True)
    balance = models.DecimalField("Баланс", max_digits=10, decimal_places=2, default=0)
    
    PLATFORM_ROLES = [
        ('student', "Студент"),
        ('support', "Поддержка"),
        ('content', "Контент-менеджер"),
        ('platform_admin', "Администратор платформы"),
    ]
    
    platform_role = models.CharField(
        "Платформенная роль", 
        max_length=20, 
        choices=PLATFORM_ROLES, 
        default='student',
        help_text="Глобальная роль на платформе"
    )
    
    bio = models.TextField("О себе", blank=True)
    company = models.CharField("Компания", max_length=100, blank=True)
    position = models.CharField("Должность", max_length=100, blank=True)
    website = models.URLField("Веб-сайт", blank=True)
    country = models.CharField("Страна", max_length=50, blank=True)
    
    segment = models.CharField("Сегмент", max_length=50, blank=True)
    last_activity = models.DateTimeField("Последняя активность", null=True, blank=True)
    
    email_notifications = models.BooleanField("Email уведомления", default=True)
    course_updates = models.BooleanField("Обновления курсов", default=True)
    newsletter = models.BooleanField("Рассылка", default=False)
    push_reminders = models.BooleanField("Напоминания", default=True)
    
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"{self.user.username} - {self.platform_role}"
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class InstructorProfile(TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="instructor_profile",
        verbose_name="Пользователь"
    )
    specialization = models.CharField("Специализация", max_length=255, blank=True)
    bio = models.TextField("О себе", blank=True)
    avatar = models.ImageField("Аватар", upload_to="instructors/", blank=True, null=True)
    experience = models.CharField("Опыт (лет)", max_length=100, blank=True, null=True)
    is_approved = models.BooleanField("Профиль подтверждён", default=False)
    approved_at = models.DateTimeField("Подтверждён", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_instructors"
    )
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        verbose_name = "Профиль инструктора"
        verbose_name_plural = "Профили инструкторов"

    def __str__(self):
        return f"Инструктор: {self.user.username}"

    def save(self, *args, **kwargs):
        if self.is_approved and not self.approved_at:
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def display_avatar_url(self) -> Optional[str]:
        try:
            return self.avatar.url if self.avatar else None
        except Exception:
            return None


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def handle_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
        logger.info(f"Profile created for user: {instance.username}")


class AuditLog(TimestampedModel):
    """Лог всех значимых действий в системе"""
    ACTION_CHOICES = [
        ('course.create', 'Создание курса'),
        ('course.update', 'Обновление курса'),
        ('course.publish', 'Публикация курса'),
        ('course.archive', 'Архивация курса'),
        ('course.delete', 'Удаление курса'),
        ('course.submit', 'Отправка курса на проверку'),
        ('course.approve', 'Одобрение курса'),
        ('enrollment.create', 'Запись на курс'),
        ('enrollment.complete', 'Завершение курса'),
        ('payment.create', 'Создание платежа'),
        ('payment.success', 'Успешный платёж'),
        ('payment.failed', 'Ошибка платежа'),
        ('payment.refund', 'Возврат платежа'),
        ('certificate.issue', 'Выдача сертификата'),
        ('certificate.revoke', 'Аннулирование сертификата'),
        ('user.role_change', 'Изменение роли пользователя'),
        ('user.delete', 'Удаление пользователя'),
        ('content.approve', 'Одобрение контента'),
        ('content.reject', 'Отклонение контента'),
        ('staff.add', 'Добавление персонала'),
        ('staff.remove', 'Удаление персонала'),
        ('progress.update', 'Обновление прогресса'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Пользователь"
    )
    ip_address = models.GenericIPAddressField("IP адрес", null=True, blank=True)
    user_agent = models.TextField("User Agent", blank=True)
    
    action = models.CharField("Действие", max_length=50, choices=ACTION_CHOICES)
    object_type = models.CharField("Тип объекта", max_length=50)
    object_id = models.CharField("ID объекта", max_length=100)
    
    before_state = models.JSONField("Состояние до", null=True, blank=True)
    after_state = models.JSONField("Состояние после", null=True, blank=True)
    changes = models.JSONField("Изменения", null=True, blank=True)
    
    metadata = models.JSONField("Метаданные", default=dict, blank=True)
    
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Лог аудита"
        verbose_name_plural = "Логи аудита"
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} by {self.user} at {self.created_at}"


class Course(TimestampedModel):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    
    STATUS_CHOICES = [
        (DRAFT, "Черновик"),
        (SUBMITTED, "Отправлен на проверку"),
        (IN_REVIEW, "На проверке"),
        (APPROVED, "Одобрен"),
        (PUBLISHED, "Опубликован"),
        (ARCHIVED, "В архиве"),
    ]
    
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    LEVEL_CHOICES = [
        (BEGINNER, "Начинающий"),
        (INTERMEDIATE, "Средний"),
        (ADVANCED, "Продвинутый"),
    ]

    title = models.CharField("Название", max_length=255)
    slug = models.SlugField("Слаг", max_length=255, unique=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
        verbose_name="Категория"
    )
    
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taught_courses",
        verbose_name="Главный инструктор"
    )

    short_description = models.CharField("Короткое описание", max_length=500, blank=True)
    description = models.TextField("Описание", blank=True)
    image = models.ImageField("Обложка", upload_to="courses/", blank=True, null=True)
    thumbnail = models.ImageField("Превью", upload_to="courses/thumbs/", blank=True, null=True)

    level = models.CharField("Уровень", max_length=20, choices=LEVEL_CHOICES, default=BEGINNER)
    duration_hours = models.PositiveIntegerField("Длительность (часы)", null=True, blank=True)
    is_featured = models.BooleanField("В подборке", default=False)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    language = models.CharField("Язык", max_length=50, default="Русский")
    certificate = models.BooleanField("Сертификат", default=True)
    
    requirements = models.TextField("Требования", blank=True)
    what_you_learn = models.TextField("Чему научитесь", blank=True)

    price = models.DecimalField("Цена", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_price = models.DecimalField("Цена со скидкой", max_digits=10, decimal_places=2, null=True, blank=True)

    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status", "is_featured"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:230]
            self.slug = base or f"course-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("course_detail", args=[self.slug])

    @property
    def display_image_url(self) -> Optional[str]:
        try:
            if self.thumbnail:
                return self.thumbnail.url
        except Exception:
            pass
        try:
            if self.image:
                return self.image.url
        except Exception:
            pass
        return None
    
    @property
    def is_published(self):
        return self.status == self.PUBLISHED
    
    @property
    def final_price(self):
        return self.discount_price if self.discount_price and self.discount_price < self.price else self.price
    
    @property
    def has_discount(self):
        return self.discount_price and self.discount_price < self.price
    
    def get_enrollment_count(self):
        return self.enrollments.count()
    
    def get_average_rating(self):
        from django.db.models import Avg
        avg = self.reviews.filter(is_active=True).aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0
    
    @property
    def enrolled_students(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(enrollments__course=self).distinct()
    
    @property
    def active_students(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(enrollments__course=self, enrollments__completed=False).distinct()
    
    @property
    def completed_students(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(enrollments__course=self, enrollments__completed=True).distinct()
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.status = self.ARCHIVED
        self.save()
    
    def submit_for_review(self):
        if self.status == self.DRAFT:
            self.status = self.SUBMITTED
            self.save()
    
    def approve(self):
        if self.status in [self.SUBMITTED, self.IN_REVIEW]:
            self.status = self.APPROVED
            self.save()
    
    def publish(self):
        if self.status in [self.APPROVED, self.DRAFT]:
            self.status = self.PUBLISHED
            self.save()
    
    def archive(self):
        self.status = self.ARCHIVED
        self.save()


class CourseStaff(TimestampedModel):
    ROLES = [
        ('owner', 'Владелец'),
        ('instructor', 'Инструктор'),
        ('assistant', 'Ассистент'),
        ('reviewer', 'Ревьюер'),
        ('support', 'Поддержка'),
    ]
    
    PERMISSIONS_CHOICES = [
        ('can_edit', 'Редактирование курса'),
        ('can_teach', 'Преподавание'),
        ('can_grade', 'Оценка работ'),
        ('can_moderate', 'Модерация'),
        ('can_view_analytics', 'Просмотр аналитики'),
        ('can_manage_students', 'Управление студентами'),
        ('can_submit', 'Отправка на проверку'),
        ('can_review', 'Проверка контента'),
        ('can_publish', 'Публикация курса'),
    ]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='staff')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_staff')
    role = models.CharField(max_length=20, choices=ROLES)
    permissions = models.JSONField(default=list)
    
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['course', 'user']
        verbose_name = 'Персонал курса'
        verbose_name_plural = 'Персонал курсов'
        indexes = [
            models.Index(fields=['course', 'user']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.get_role_display()} ({self.course.title})"
    
    def has_permission(self, permission):
        return permission in self.permissions
    
    def clean(self):
        role_permissions = {
            'owner': ['can_edit', 'can_teach', 'can_grade', 'can_moderate', 'can_view_analytics', 'can_manage_students', 'can_submit', 'can_review', 'can_publish'],
            'instructor': ['can_teach', 'can_grade', 'can_moderate', 'can_view_analytics', 'can_manage_students', 'can_submit'],
            'assistant': ['can_grade', 'can_moderate'],
            'reviewer': ['can_grade', 'can_review'],
            'support': ['can_view_analytics'],
        }
        
        valid_permissions = role_permissions.get(self.role, [])
        invalid_permissions = [p for p in self.permissions if p not in valid_permissions]
        
        if invalid_permissions:
            raise ValidationError({
                'permissions': f"Role '{self.get_role_display()}' cannot have permissions: {', '.join(invalid_permissions)}"
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Module(TimestampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules", verbose_name="Курс")
    title = models.CharField("Название модуля", max_length=255)
    order = models.PositiveIntegerField("Порядок", default=1)
    is_active = models.BooleanField("Активен", default=True)
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Модуль"
        verbose_name_plural = "Модули"
        unique_together = [("course", "order")]
        indexes = [
            models.Index(fields=["course", "order"]),
        ]

    def __str__(self):
        return f"{self.course.title} — {self.title}"
    
    def get_lesson_count(self):
        return self.lessons.filter(is_active=True, is_deleted=False).count()
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class Lesson(TimestampedModel):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons", verbose_name="Модуль")
    title = models.CharField("Название урока", max_length=255)
    slug = models.SlugField("Слаг", max_length=255, blank=True)
    order = models.PositiveIntegerField("Порядок", default=1)
    
    description = models.TextField("Описание", blank=True)
    duration_minutes = models.PositiveIntegerField("Длительность (мин.)", null=True, blank=True)
    
    is_active = models.BooleanField("Активен", default=True)
    is_free = models.BooleanField("Бесплатный", default=False)
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)
    
    free_preview_blocks = models.PositiveIntegerField(
        "Бесплатных блоков для превью",
        default=1,
        help_text="Сколько первых блоков доступны бесплатно"
    )

    class Meta:
        ordering = ["module__order", "order", "id"]
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
        unique_together = [("module", "slug")]
        indexes = [
            models.Index(fields=["module", "order"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:230]
            self.slug = base or f"lesson-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse("lesson_detail", args=[self.module.course.slug, self.slug])
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class LessonBlock(TimestampedModel):
    BLOCK_TYPES = [
        ('text', "Текст"),
        ('video', "Видео"),
        ('file', "Файл"),
        ('quiz', "Тест"),
        ('assignment', "Задание"),
        ('code', "Код"),
        ('embed', "Embed (iframe)"),
    ]
    
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="blocks")
    block_type = models.CharField("Тип блока", max_length=20, choices=BLOCK_TYPES, default='text')
    order = models.PositiveIntegerField("Порядок", default=1)
    
    title = models.CharField("Заголовок", max_length=255, blank=True)
    description = models.TextField("Описание", blank=True)
    
    content = models.TextField("Содержимое", blank=True)
    video_url = models.URLField("URL видео", blank=True)
    embed_url = models.URLField("Embed URL", blank=True)
    file = models.FileField("Файл", upload_to="lesson_blocks/", blank=True, null=True)
    
    quiz = models.ForeignKey('Quiz', on_delete=models.SET_NULL, null=True, blank=True, related_name="blocks")
    assignment = models.ForeignKey('Assignment', on_delete=models.SET_NULL, null=True, blank=True, related_name="blocks")
    
    is_required = models.BooleanField("Обязательный", default=True)
    estimated_minutes = models.PositiveIntegerField("Примерное время (мин)", default=10)
    is_free_preview = models.BooleanField("Бесплатный превью", default=False)
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "Блок урока"
        verbose_name_plural = "Блоки уроков"
        indexes = [
            models.Index(fields=["lesson", "order"]),
            models.Index(fields=["lesson", "block_type"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["lesson", "order"], name="uniq_block_order"),
        ]

    def __str__(self):
        return f"{self.get_block_type_display()}: {self.title or 'Блок'} ({self.lesson.title})"
    
    def clean(self):
        if self.block_type == 'video' and not self.video_url:
            raise ValidationError({'video_url': 'Для видео-блока требуется URL видео'})
        if self.block_type == 'embed' and not self.embed_url:
            raise ValidationError({'embed_url': 'Для embed-блока требуется URL'})
    
    @property
    def display_content(self):
        if self.block_type == 'text':
            return self.content
        elif self.block_type == 'video':
            return f'<video src="{self.video_url}">'
        elif self.block_type == 'file':
            return f'<a href="{self.file.url}">Скачать файл</a>' if self.file else ''
        elif self.block_type == 'embed':
            return f'<iframe src="{self.embed_url}"></iframe>'
        return ''
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class BlockProgress(TimestampedModel):
    """Прогресс по каждому блоку"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="block_progress")
    block = models.ForeignKey(LessonBlock, on_delete=models.CASCADE, related_name="progress")
    
    is_completed = models.BooleanField("Завершён", default=False)
    progress_percent = models.PositiveIntegerField("Прогресс, %", default=0)
    completed_at = models.DateTimeField("Завершён", null=True, blank=True)
    
    time_spent = models.PositiveIntegerField("Потрачено времени (сек)", default=0)
    last_accessed = models.DateTimeField("Последний доступ", auto_now=True)
    
    metadata = models.JSONField("Метаданные", default=dict, blank=True)

    class Meta:
        verbose_name = "Прогресс по блоку"
        verbose_name_plural = "Прогресс по блокам"
        constraints = [
            models.UniqueConstraint(fields=["user", "block"], name="uniq_block_progress_user_block"),
        ]
        indexes = [
            models.Index(fields=["user", "block"]),
            models.Index(fields=["is_completed", "completed_at"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.block} ({self.progress_percent}%)"
    
    def save(self, *args, **kwargs):
        if self.progress_percent >= 100 and not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
        elif self.is_completed and self.progress_percent < 100:
            self.progress_percent = 100
        super().save(*args, **kwargs)


class Enrollment(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments", verbose_name="Пользователь")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments", verbose_name="Курс")
    
    completed = models.BooleanField("Курс завершён", default=False)
    completed_at = models.DateTimeField("Завершён", null=True, blank=True)
    
    enrolled_at = models.DateTimeField("Записан", auto_now_add=True)
    accessed_at = models.DateTimeField("Последний доступ", null=True, blank=True)
    
    notifications_enabled = models.BooleanField("Уведомления", default=True)
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        verbose_name = "Запись на курс"
        verbose_name_plural = "Записи на курсы"
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_enrollment_user_course"),
        ]
        indexes = [
            models.Index(fields=["user", "course"]),
            models.Index(fields=["completed", "completed_at"]),
        ]

    def __str__(self):
        return f"{self.user} → {self.course}"
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class Review(TimestampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="reviews", verbose_name="Курс")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
        verbose_name="Пользователь"
    )
    
    rating = models.PositiveSmallIntegerField("Оценка (1–5)", choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField("Отзыв", blank=True)
    
    is_active = models.BooleanField("Показывать", default=True)
    moderated_at = models.DateTimeField("Промодерирован", null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_reviews"
    )
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        indexes = [
            models.Index(fields=["course", "is_active"]),
            models.Index(fields=["rating"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["course", "user"], name="uniq_review_course_user"),
        ]

    def __str__(self):
        return f"Отзыв {self.user} о {self.course} — {self.rating}⭐"
    
    def clean(self):
        if self.rating < 1 or self.rating > 5:
            raise ValidationError({'rating': 'Rating must be between 1 and 5'})
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class Wishlist(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist", verbose_name="Пользователь")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="wishlisted_in", verbose_name="Курс")
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_wishlist_user_course"),
        ]
        indexes = [
            models.Index(fields=["user", "course"]),
        ]

    def __str__(self):
        return f"★ {self.user} — {self.course}"
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class Payment(TimestampedModel):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    STATUS_CHOICES = [
        (PENDING, "В ожидании"),
        (SUCCESS, "Успешно"),
        (FAILED, "Ошибка"),
        (REFUNDED, "Возвращён"),
    ]

    CARD = "card"
    KASPI = "kaspi"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"
    TYPE_CHOICES = [
        (CARD, "Карта"),
        (KASPI, "Kaspi"),
        (BANK_TRANSFER, "Банковский перевод"),
        (WALLET, "Кошелёк"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments", verbose_name="Пользователь")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="payments", verbose_name="Курс")
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    
    status = models.CharField("Статус", max_length=16, choices=STATUS_CHOICES, default=PENDING)
    type = models.CharField("Тип оплаты", max_length=20, choices=TYPE_CHOICES, default=KASPI)
    
    payment_id = models.CharField("ID платежа", max_length=255, unique=True, blank=True)
    kaspi_invoice_id = models.CharField("Kaspi invoice ID", max_length=255, null=True, blank=True, unique=True)
    
    idempotency_key = models.CharField(
        "Ключ идемпотентности",
        max_length=100,
        unique=True,
        blank=True,
        help_text="Предотвращает дублирование платежей"
    )
    
    external_id = models.CharField(
        "Внешний ID",
        max_length=255,
        blank=True,
        help_text="ID платежа во внешней системе"
    )
    
    receipt = models.FileField("Чек", upload_to="payments/receipts/", blank=True, null=True)
    
    paid_at = models.DateTimeField("Оплачено", null=True, blank=True)
    refunded_at = models.DateTimeField("Возвращено", null=True, blank=True)
    
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        indexes = [
            models.Index(fields=["payment_id"]),
            models.Index(fields=["kaspi_invoice_id"]),
            models.Index(fields=["user", "course"]),
            models.Index(fields=["status", "paid_at"]),
            models.Index(fields=["idempotency_key"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.course} — {self.amount} ({self.status})"
    
    def save(self, *args, **kwargs):
        if not self.payment_id:
            self.payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        
        if not self.idempotency_key:
            self.idempotency_key = f"pay_{uuid.uuid4().hex}"
        
        if self.status == self.SUCCESS:
            existing = Payment.objects.filter(
                idempotency_key=self.idempotency_key,
                status=self.SUCCESS
            ).exclude(id=self.id if self.id else None).exists()
            
            if existing:
                raise ValidationError("Дублирующийся платеж")
            
            if not self.paid_at:
                self.paid_at = timezone.now()
            
        elif self.status == self.REFUNDED and not self.refunded_at:
            self.refunded_at = timezone.now()
            
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class ContactMessage(TimestampedModel):
    name = models.CharField("Имя", max_length=120)
    email = models.EmailField("Email")
    subject = models.CharField("Тема", max_length=200)
    message = models.TextField("Сообщение")
    
    is_processed = models.BooleanField("Обработано", default=False)
    processed_at = models.DateTimeField("Обработано", null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_messages"
    )
    response = models.TextField("Ответ", blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Сообщение контактов"
        verbose_name_plural = "Сообщения контактов"

    def __str__(self):
        return f"{self.email}: {self.subject}"


try:
    from ckeditor_uploader.fields import RichTextUploadingField
    _RichField = RichTextUploadingField
except ImportError:
    _RichField = models.TextField


class Article(TimestampedModel):
    DRAFT = "draft"
    PUBLISHED = "published"
    STATUS_CHOICES = [(DRAFT, "Черновик"), (PUBLISHED, "Опубликовано")]

    title = models.CharField("Заголовок", max_length=255)
    slug = models.SlugField("Слаг", max_length=255, unique=True, blank=True)
    
    excerpt = models.TextField("Краткое описание", blank=True)
    body = _RichField("Текст", blank=True)
    cover = models.ImageField("Обложка", upload_to="articles/", blank=True, null=True)
    
    view_count = models.PositiveIntegerField("Просмотры", default=0)
    
    seo_title = models.CharField("SEO Title", max_length=255, blank=True)
    seo_description = models.CharField("SEO Description", max_length=500, blank=True)
    seo_keywords = models.CharField("SEO Keywords", max_length=500, blank=True)
    seo_schema = models.TextField("SEO Schema (JSON-LD)", blank=True)
    
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    published_at = models.DateTimeField("Опубликовано", blank=True, null=True)

    
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "published_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:250] or f"article-{uuid.uuid4().hex[:8]}"
        
        if self.status == self.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
            
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("article_detail", args=[self.slug])
    
    def increment_view_count(self):
        Article.objects.filter(id=self.id).update(view_count=models.F('view_count') + 1)
        self.refresh_from_db()
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class Material(TimestampedModel):
    title = models.CharField("Название", max_length=200)
    slug = models.SlugField("Слаг", max_length=220, unique=True)
    description = models.TextField("Описание", blank=True)
    
    file = models.FileField("Файл", upload_to="materials/files/", blank=True, null=True)
    image = models.ImageField("Превью", upload_to="materials/images/", blank=True, null=True)
    
    is_public = models.BooleanField("Показывать на сайте", default=True)
    download_count = models.PositiveIntegerField("Скачивания", default=0)
    
    category = models.CharField("Категория", max_length=100, blank=True)
    tags = models.JSONField("Теги", default=list, blank=True)
    
    is_deleted = models.BooleanField("Удалён", default=False)
    deleted_at = models.DateTimeField("Удалён", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Материал"
        verbose_name_plural = "Материалы"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["category", "is_public"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or f"material-{uuid.uuid4().hex[:8]}"
            self.slug = base
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("materials_list") + f"#{self.slug}"
    
    def increment_download_count(self):
        Material.objects.filter(id=self.id).update(download_count=models.F('download_count') + 1)
        self.refresh_from_db()
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()


class Quiz(TimestampedModel):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="quizzes")
    title = models.CharField("Название теста", max_length=255)
    
    passing_score = models.PositiveIntegerField("Проходной балл", default=70)
    time_limit = models.PositiveIntegerField("Лимит времени (мин)", null=True, blank=True)
    attempts_allowed = models.PositiveIntegerField("Попыток разрешено", default=1)
    is_active = models.BooleanField("Активен", default=True)
    
    description = models.TextField("Описание", blank=True)
    instructions = models.TextField("Инструкции", blank=True)

    class Meta:
        verbose_name = "Тест"
        verbose_name_plural = "Тесты"
        ordering = ["lesson", "title"]

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"
    
    def get_question_count(self):
        return self.questions.count()
    
    def get_total_points(self):
        return self.questions.aggregate(total=models.Sum('points'))['total'] or 0


class Question(TimestampedModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField("Вопрос")
    
    QUESTION_TYPES = [
        ('single', "Один вариант"),
        ('multiple', "Несколько вариантов"),
        ('text', "Текстовый ответ"),
        ('code', "Код"),
    ]
    question_type = models.CharField("Тип вопроса", max_length=20, choices=QUESTION_TYPES, default='single')
    
    order = models.PositiveIntegerField("Порядок", default=1)
    points = models.PositiveIntegerField("Баллы", default=1)
    explanation = models.TextField("Объяснение", blank=True)

    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"
        ordering = ["quiz", "order"]

    def __str__(self):
        return f"{self.quiz.title} - {self.text[:50]}..."


class Answer(TimestampedModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    text = models.CharField("Ответ", max_length=500)
    is_correct = models.BooleanField("Правильный ответ", default=False)
    order = models.PositiveIntegerField("Порядок", default=1)
    
    correct_answer = models.TextField("Правильный ответ (для текста)", blank=True)

    class Meta:
        verbose_name = "Ответ"
        verbose_name_plural = "Ответы"
        ordering = ["question", "order"]

    def __str__(self):
        return f"{self.question.text[:30]} - {self.text[:30]}"


class Assignment(TimestampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField("Название задания", max_length=255)
    description = models.TextField("Описание")
    
    due_date = models.DateTimeField("Срок сдачи")
    max_points = models.PositiveIntegerField("Максимум баллов", default=100)
    is_active = models.BooleanField("Активно", default=True)
    
    instructions = models.TextField("Инструкции", blank=True)
    attachments = models.FileField("Приложения", upload_to="assignments/", blank=True, null=True)

    class Meta:
        verbose_name = "Домашнее задание"
        verbose_name_plural = "Домашние задания"
        ordering = ["course", "-due_date"]

    def __str__(self):
        return f"{self.course.title} - {self.title}"
    
    @property
    def is_overdue(self):
        return timezone.now() > self.due_date if self.due_date else False


class Submission(TimestampedModel):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions")
    
    file = models.FileField("Файл работы", upload_to="submissions/", blank=True, null=True)
    text = models.TextField("Текст работы", blank=True)
    url = models.URLField("Ссылка на работу", blank=True)
    
    grade = models.PositiveIntegerField("Оценка", null=True, blank=True)
    feedback = models.TextField("Обратная связь", blank=True)
    graded_at = models.DateTimeField("Оценено", null=True, blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions"
    )
    
    submitted_at = models.DateTimeField("Время отправки", auto_now_add=True)

    class Meta:
        verbose_name = "Сданная работа"
        verbose_name_plural = "Сданные работы"
        constraints = [
            models.UniqueConstraint(fields=["assignment", "user"], name="uniq_submission_assignment_user"),
        ]
        indexes = [
            models.Index(fields=["assignment", "user"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.assignment.title}"
    
    @property
    def is_graded(self):
        return self.grade is not None
    
    @property
    def is_late(self):
        return self.submitted_at > self.assignment.due_date if self.assignment.due_date else False


class Certificate(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    
    certificate_id = models.CharField("ID сертификата", max_length=100, unique=True)
    pdf_file = models.FileField("PDF файл", upload_to="certificates/", blank=True, null=True)
    
    is_revoked = models.BooleanField("Аннулирован", default=False)
    revoked_at = models.DateTimeField("Аннулирован", null=True, blank=True)
    revoked_reason = models.TextField("Причина аннулирования", blank=True)
    
    issued_at = models.DateTimeField("Выдан", auto_now_add=True)

    class Meta:
        verbose_name = "Сертификат"
        verbose_name_plural = "Сертификаты"
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_certificate_user_course"),
        ]
        indexes = [
            models.Index(fields=["certificate_id"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.course.title}"
    
    def save(self, *args, **kwargs):
        if not self.certificate_id:
            self.certificate_id = f"CERT-{uuid.uuid4().hex[:16].upper()}"
        super().save(*args, **kwargs)


class Lead(TimestampedModel):
    email = models.EmailField("Email")
    name = models.CharField("Имя", max_length=120)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    
    source = models.CharField("Источник", max_length=100, default="website")
    campaign = models.CharField("Кампания", max_length=100, blank=True)
    
    STATUS_CHOICES = [
        ('new', "Новый"),
        ('contacted', "Связались"),
        ('qualified', "Квалифицирован"),
        ('converted', "Конвертирован"),
        ('lost', "Потерян"),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='new')
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_leads"
    )
    converted = models.BooleanField("Конвертирован", default=False)
    converted_at = models.DateTimeField("Конвертирован", null=True, blank=True)
    
    notes = models.TextField("Заметки", blank=True)
    tags = models.JSONField("Теги", default=list, blank=True)

    class Meta:
        verbose_name = "Лид"
        verbose_name_plural = "Лиды"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "converted"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.email}"


class Interaction(TimestampedModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="interactions")
    
    TYPE_CHOICES = [
        ('call', "Звонок"),
        ('email', "Email"),
        ('meeting', "Встреча"),
        ('message', "Сообщение"),
        ('note', "Заметка"),
    ]
    type = models.CharField("Тип взаимодействия", max_length=20, choices=TYPE_CHOICES)
    
    description = models.TextField("Описание")
    result = models.CharField("Результат", max_length=200, blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interactions")
    
    follow_up_date = models.DateTimeField("Дата следующего контакта", null=True, blank=True)
    is_completed = models.BooleanField("Завершено", default=False)

    class Meta:
        verbose_name = "Взаимодействие"
        verbose_name_plural = "Взаимодействия"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.lead.name} - {self.type}"


class Segment(TimestampedModel):
    name = models.CharField("Название", max_length=100)
    description = models.TextField("Описание", blank=True)
    
    conditions = models.JSONField("Условия", default=dict)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="segments", blank=True)
    
    is_active = models.BooleanField("Активен", default=True)
    is_dynamic = models.BooleanField("Динамический", default=True)
    
    user_count = models.PositiveIntegerField("Пользователей", default=0)

    class Meta:
        verbose_name = "Сегмент"
        verbose_name_plural = "Сегменты"

    def __str__(self):
        return self.name
    
    def update_user_count(self):
        self.user_count = self.users.count()
        self.save(update_fields=['user_count'])


class SupportTicket(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_tickets")
    
    ticket_id = models.CharField("ID тикета", max_length=50, unique=True, blank=True)
    subject = models.CharField("Тема", max_length=200)
    description = models.TextField("Описание проблемы")
    
    STATUS_CHOICES = [
        ('open', "Открыт"),
        ('in_progress', "В работе"),
        ('resolved', "Решен"),
        ('closed', "Закрыт"),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='open')
    
    PRIORITY_CHOICES = [
        ('low', "Низкий"),
        ('medium', "Средний"),
        ('high', "Высокий"),
        ('urgent', "Срочный"),
    ]
    priority = models.CharField("Приоритет", max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    category = models.CharField("Категория", max_length=50, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets"
    )
    
    resolved_at = models.DateTimeField("Решен", null=True, blank=True)
    closed_at = models.DateTimeField("Закрыт", null=True, blank=True)

    class Meta:
        verbose_name = "Тикет поддержки"
        verbose_name_plural = "Тикеты поддержки"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["ticket_id"]),
            models.Index(fields=["status", "priority"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.subject}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = f"TICKET-{uuid.uuid4().hex[:12].upper()}"
        
        if self.status == 'resolved' and not self.resolved_at:
            self.resolved_at = timezone.now()
        elif self.status == 'closed' and not self.closed_at:
            self.closed_at = timezone.now()
            
        super().save(*args, **kwargs)


class FAQ(TimestampedModel):
    question = models.CharField("Вопрос", max_length=500)
    answer = models.TextField("Ответ")
    
    category = models.CharField("Категория", max_length=100)
    order = models.PositiveIntegerField("Порядок", default=1)
    
    is_active = models.BooleanField("Активен", default=True)
    view_count = models.PositiveIntegerField("Просмотры", default=0)
    
    tags = models.JSONField("Теги", default=list, blank=True)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQ"
        ordering = ["category", "order"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self):
        return self.question


class Plan(TimestampedModel):
    name = models.CharField("Название", max_length=100)
    description = models.TextField("Описание", blank=True)
    
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField("Длительность (дни)")
    
    features = models.JSONField("Возможности", default=list)
    
    is_active = models.BooleanField("Активен", default=True)
    is_popular = models.BooleanField("Популярный", default=False)
    
    max_courses = models.PositiveIntegerField("Макс. курсов", null=True, blank=True)
    max_students = models.PositiveIntegerField("Макс. студентов", null=True, blank=True)

    class Meta:
        verbose_name = "Тарифный план"
        verbose_name_plural = "Тарифные планы"

    def __str__(self):
        return self.name
    
    @property
    def monthly_price(self):
        if self.duration_days >= 30:
            return self.price / (self.duration_days / 30)
        return self.price


class Subscription(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="subscriptions")
    
    STATUS_CHOICES = [
        ('active', "Активна"),
        ('canceled', "Отменена"),
        ('expired', "Истекла"),
        ('pending', "Ожидание"),
        ('trial', "Пробный период"),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='pending')
    
    start_date = models.DateTimeField("Начало")
    end_date = models.DateTimeField("Окончание")
    trial_end_date = models.DateTimeField("Конец пробного периода", null=True, blank=True)
    
    auto_renew = models.BooleanField("Автопродление", default=True)
    cancel_at_period_end = models.BooleanField("Отменить в конце периода", default=False)

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["end_date", "status"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"
    
    @property
    def is_active(self):
        return self.status == 'active' and self.end_date > timezone.now()
    
    @property
    def days_remaining(self):
        if self.end_date:
            delta = self.end_date - timezone.now()
            return max(0, delta.days)
        return 0


class Refund(TimestampedModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="refunds")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="refunds")
    
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    reason = models.TextField("Причина")
    
    STATUS_CHOICES = [
        ('pending', "На рассмотрении"),
        ('approved', "Одобрен"),
        ('rejected', "Отклонен"),
        ('processed', "Обработан"),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='pending')
    
    processed_at = models.DateTimeField("Обработан", null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_refunds"
    )
    notes = models.TextField("Заметки", blank=True)

    class Meta:
        verbose_name = "Возврат"
        verbose_name_plural = "Возвраты"
        indexes = [
            models.Index(fields=["payment", "status"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.amount}"


class Mailing(TimestampedModel):
    subject = models.CharField("Тема", max_length=200)
    message = models.TextField("Сообщение")
    
    CHANNEL_CHOICES = [
        ('email', "Email"),
        ('telegram', "Telegram"),
        ('push', "Push-уведомление"),
        ('sms', "SMS"),
    ]
    channel = models.CharField("Канал", max_length=20, choices=CHANNEL_CHOICES, default='email')
    
    segment = models.ForeignKey(Segment, on_delete=models.CASCADE, related_name="mailings", null=True, blank=True)
    
    STATUS_CHOICES = [
        ('draft', "Черновик"),
        ('scheduled', "Запланирована"),
        ('sending', "Отправляется"),
        ('sent', "Отправлена"),
        ('canceled', "Отменена"),
        ('failed', "Ошибка"),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='draft')
    
    scheduled_for = models.DateTimeField("Запланирована на", null=True, blank=True)
    sent_at = models.DateTimeField("Отправлено", null=True, blank=True)
    
    sent = models.PositiveIntegerField("Отправлено", default=0)
    opens = models.PositiveIntegerField("Открытия", default=0)
    clicks = models.PositiveIntegerField("Клики", default=0)
    unsubscribes = models.PositiveIntegerField("Отписки", default=0)

    class Meta:
        verbose_name = "Рассылка"
        verbose_name_plural = "Рассылки"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_for"]),
        ]

    def __str__(self):
        return self.subject

    @property
    def open_percentage(self):
        return round((self.opens / self.sent * 100), 2) if self.sent > 0 else 0
    
    @property
    def click_percentage(self):
        return round((self.clicks / self.sent * 100), 2) if self.sent > 0 else 0
    
    def mark_as_sent(self, sent_count):
        self.status = 'sent'
        self.sent = sent_count
        self.sent_at = timezone.now()
        self.save()


@receiver(post_save, sender=Course)
def create_course_staff(sender, instance, created, **kwargs):
    if created and instance.instructor:
        CourseStaff.objects.get_or_create(
            course=instance,
            user=instance.instructor,
            defaults={
                'role': 'owner',
                'permissions': ['can_edit', 'can_teach', 'can_grade', 'can_moderate', 'can_view_analytics', 'can_manage_students', 'can_submit', 'can_review', 'can_publish']
            }
        )


def get_user_permissions(user, course=None):
    permissions = {
        'global': {
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'platform_role': user.profile.platform_role if hasattr(user, 'profile') else 'student',
        },
        'course': {}
    }
    
    if course:
        staff = CourseStaff.objects.filter(course=course, user=user, is_active=True).first()
        if staff:
            permissions['course'] = {
                'role': staff.role,
                'permissions': staff.permissions,
                'is_owner': staff.role == 'owner',
                'is_instructor': staff.role in ['owner', 'instructor'],
                'can_edit': 'can_edit' in staff.permissions,
                'can_teach': 'can_teach' in staff.permissions,
                'can_grade': 'can_grade' in staff.permissions,
                'can_moderate': 'can_moderate' in staff.permissions,
                'can_view_analytics': 'can_view_analytics' in staff.permissions,
                'can_manage_students': 'can_manage_students' in staff.permissions,
                'can_submit': 'can_submit' in staff.permissions,
                'can_review': 'can_review' in staff.permissions,
                'can_publish': 'can_publish' in staff.permissions,
            }
    
    return permissions


def can_user_access_course(user, course):
    if user.is_superuser or user.is_staff:
        return True
    
    if CourseStaff.objects.filter(course=course, user=user, is_active=True).exists():
        return True
    
    if course.is_published:
        return True
    
    return Enrollment.objects.filter(user=user, course=course).exists()


def get_user_courses(user, role='student'):
    if role == 'student':
        return Course.objects.filter(
            enrollments__user=user,
            status=Course.PUBLISHED
        ).distinct()
    
    elif role == 'instructor':
        return Course.objects.filter(
            staff__user=user,
            staff__role__in=['owner', 'instructor'],
            staff__is_active=True
        ).distinct()
    
    elif role == 'staff':
        return Course.objects.filter(
            staff__user=user,
            staff__is_active=True
        ).distinct()
    
    return Course.objects.none()


def require_course_permission(user, course, permission):
    """Guard для проверки прав на уровне объекта"""
    if user.is_superuser or user.is_staff:
        return True
    
    if not hasattr(user, 'profile'):
        raise PermissionDenied("User profile not found")
    
    if user.profile.platform_role == 'platform_admin':
        return True
    
    staff = CourseStaff.objects.filter(course=course, user=user, is_active=True).first()
    if not staff:
        raise PermissionDenied(f"No staff access to course {course.id}")
    
    if permission not in staff.permissions:
        raise PermissionDenied(f"Missing permission: {permission}")
    
    return True


def log_audit_event(user, action, obj, metadata=None, request=None):
    """Создание записи в логе аудита"""
    audit_log = AuditLog(
        user=user,
        action=action,
        object_type=obj.__class__.__name__,
        object_id=str(obj.id),
        metadata=metadata or {},
    )
    
    if request:
        audit_log.ip_address = request.META.get('REMOTE_ADDR')
        audit_log.user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    audit_log.save()
    return audit_log