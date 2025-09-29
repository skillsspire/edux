from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

User = settings.AUTH_USER_MODEL


# =========================
#      БАЗОВЫЕ МОДЕЛИ
# =========================

class TimestampedModel(models.Model):
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        abstract = True


class Category(TimestampedModel):
    name = models.CharField("Название", max_length=150, unique=True)
    slug = models.SlugField("Слаг", max_length=160, unique=True, blank=True)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:155]
        super().save(*args, **kwargs)


class InstructorProfile(TimestampedModel):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="instructor_profile", verbose_name="Пользователь"
    )
    specialization = models.CharField("Специализация", max_length=255, blank=True)
    bio = models.TextField("О себе", blank=True)
    avatar = models.ImageField("Аватар", upload_to="instructors/", blank=True, null=True)
    is_approved = models.BooleanField("Профиль подтверждён", default=True)

    class Meta:
        verbose_name = "Профиль инструктора"
        verbose_name_plural = "Профили инструкторов"

    def __str__(self):
        return f"Инструктор: {getattr(self.user, 'username', 'user')}"

    @property
    def display_avatar_url(self) -> Optional[str]:
        try:
            return self.avatar.url if self.avatar else None
        except Exception:
            return None


# =========================
#          КУРСЫ
# =========================

class Course(TimestampedModel):
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
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="courses")
    instructor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="taught_courses", verbose_name="Инструктор"
    )

    short_description = models.CharField("Короткое описание", max_length=500, blank=True)
    description = models.TextField("Описание", blank=True)

    # Медиа
    image = models.ImageField("Обложка", upload_to="courses/", blank=True, null=True)
    thumbnail = models.ImageField("Превью", upload_to="courses/thumbs/", blank=True, null=True)

    # Метаданные
    level = models.CharField("Уровень", max_length=20, choices=LEVEL_CHOICES, default=BEGINNER)
    duration_hours = models.PositiveIntegerField("Длительность (часы)", null=True, blank=True)
    is_featured = models.BooleanField("В подборке", default=False)

    # Цены
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_price = models.DecimalField("Цена со скидкой", max_digits=10, decimal_places=2, null=True, blank=True)

    # Записанные студенты (через Enrollment)
    students = models.ManyToManyField(
        User, through="Enrollment", related_name="enrolled_courses", blank=True, verbose_name="Студенты"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:230]
            self.slug = base or f"course-{int(timezone.now().timestamp())}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("course_detail", args=[self.slug])

    @property
    def display_image_url(self) -> Optional[str]:
        """Без внешних хелперов: отдаём thumbnail/url, если настроено хранилище."""
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


class Module(TimestampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules", verbose_name="Курс")
    title = models.CharField("Название модуля", max_length=255)
    order = models.PositiveIntegerField("Порядок", default=1)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Модуль"
        verbose_name_plural = "Модули"
        unique_together = [("course", "order")]

    def __str__(self):
        return f"{self.course.title} — {self.title}"


class Lesson(TimestampedModel):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons", verbose_name="Модуль")
    title = models.CharField("Название урока", max_length=255)
    slug = models.SlugField("Слаг", max_length=255, blank=True)
    order = models.PositiveIntegerField("Порядок", default=1)
    duration_minutes = models.PositiveIntegerField("Длительность (мин.)", null=True, blank=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        ordering = ["module__order", "order", "id"]
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
        unique_together = [("module", "slug")]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:230]
            self.slug = base or f"lesson-{int(timezone.now().timestamp())}"
        super().save(*args, **kwargs)


class Enrollment(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments", verbose_name="Пользователь")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments", verbose_name="Курс")
    completed = models.BooleanField("Курс завершён", default=False)

    class Meta:
        verbose_name = "Запись на курс"
        verbose_name_plural = "Записи на курсы"
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_enrollment_user_course"),
        ]
        indexes = [
            models.Index(fields=["user", "course"]),
        ]

    def __str__(self):
        return f"{self.user} → {self.course}"


class LessonProgress(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="lesson_progress", verbose_name="Пользователь")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress", verbose_name="Урок")
    is_completed = models.BooleanField("Завершён", default=False)
    percent = models.PositiveIntegerField("Прогресс, %", default=0)

    class Meta:
        verbose_name = "Прогресс по уроку"
        verbose_name_plural = "Прогресс по урокам"
        constraints = [
            models.UniqueConstraint(fields=["user", "lesson"], name="uniq_progress_user_lesson"),
        ]

    def __str__(self):
        return f"{self.user} — {self.lesson} ({self.percent}%)"


# =========================
#      ОТЗЫВЫ/ИЗБРАННОЕ
# =========================

class Review(TimestampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="reviews", verbose_name="Курс")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews",
                             verbose_name="Пользователь")
    rating = models.PositiveSmallIntegerField("Оценка (1–5)", default=5)
    comment = models.TextField("Отзыв", blank=True)
    is_active = models.BooleanField("Показывать", default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        indexes = [models.Index(fields=["course"])]

    def __str__(self):
        return f"Отзыв {self.user} о {self.course} — {self.rating}"


class Wishlist(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishlist", verbose_name="Пользователь")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="wishlisted_in", verbose_name="Курс")

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_wishlist_user_course"),
        ]

    def __str__(self):
        return f"★ {self.user} — {self.course}"


# =========================
#          ОПЛАТЫ
# =========================

class Payment(TimestampedModel):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    STATUS_CHOICES = [
        (PENDING, "В ожидании"),
        (SUCCESS, "Успешно"),
        (FAILED, "Ошибка"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments", verbose_name="Пользователь")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="payments", verbose_name="Курс")
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("Статус", max_length=16, choices=STATUS_CHOICES, default=PENDING)
    kaspi_invoice_id = models.CharField("Kaspi invoice ID", max_length=64, unique=True)
    receipt = models.FileField("Чек", upload_to="payments/receipts/", blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        indexes = [
            models.Index(fields=["kaspi_invoice_id"]),
            models.Index(fields=["user", "course"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.course} — {self.amount} ({self.status})"


# =========================
#     КОНТАКТЫ/СТАТЬИ
# =========================

class ContactMessage(TimestampedModel):
    name = models.CharField("Имя", max_length=120)
    email = models.EmailField("Email")
    subject = models.CharField("Тема", max_length=200)
    message = models.TextField("Сообщение")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Сообщение контактов"
        verbose_name_plural = "Сообщения контактов"

    def __str__(self):
        return f"{self.email}: {self.subject}"


# Опционально: CKEditor, если подключён
try:
    from ckeditor_uploader.fields import RichTextUploadingField  # type: ignore
    _RichField = RichTextUploadingField
except Exception:
    _RichField = models.TextField  # fallback на обычный текст


class Article(TimestampedModel):
    DRAFT = "draft"
    PUBLISHED = "published"
    STATUS_CHOICES = [(DRAFT, "Черновик"), (PUBLISHED, "Опубликовано")]

    title = models.CharField("Заголовок", max_length=255)
    slug = models.SlugField("Слаг", max_length=255, unique=True, blank=True)
    excerpt = models.TextField("Краткое описание", blank=True)
    body = _RichField("Текст", blank=True)  # CKEditor если есть, иначе TextField
    cover = models.ImageField("Обложка", upload_to="articles/", blank=True, null=True)

    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    published_at = models.DateTimeField("Опубликовано", blank=True, null=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        indexes = [models.Index(fields=["slug"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:250]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("articles_detail", args=[self.slug])


# =========================
#          МАТЕРИАЛЫ
# =========================

class Material(TimestampedModel):
    title = models.CharField("Название", max_length=200)
    slug = models.SlugField("Слаг", max_length=220, unique=True)
    description = models.TextField("Описание", blank=True)
    file = models.FileField("Файл", upload_to="materials/files/", blank=True, null=True)
    image = models.ImageField("Превью", upload_to="materials/images/", blank=True, null=True)
    is_public = models.BooleanField("Показывать на сайте", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Материал"
        verbose_name_plural = "Материалы"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("materials_list") + f"#{self.slug}"