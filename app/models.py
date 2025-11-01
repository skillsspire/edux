from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

User = settings.AUTH_USER_MODEL


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
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="instructor_profile", verbose_name="Пользователь")
    specialization = models.CharField("Специализация", max_length=255, blank=True)
    bio = models.TextField("О себе", blank=True)
    avatar = models.ImageField("Аватар", upload_to="instructors/", blank=True, null=True)
    is_approved = models.BooleanField("Профиль подтверждён", default=True)

    # 🧩 добавь обратно:
    experience = models.CharField("Опыт (лет)", max_length=100, blank=True, null=True)

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
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="courses"
    )
    instructor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taught_courses",
        verbose_name="Инструктор",
    )

    short_description = models.CharField("Короткое описание", max_length=500, blank=True)
    description = models.TextField("Описание", blank=True)

    image = models.ImageField("Обложка", upload_to="courses/", blank=True, null=True)
    thumbnail = models.ImageField("Превью", upload_to="courses/thumbs/", blank=True, null=True)

    level = models.CharField("Уровень", max_length=20, choices=LEVEL_CHOICES, default=BEGINNER)
    duration_hours = models.PositiveIntegerField("Длительность (часы)", null=True, blank=True)
    is_featured = models.BooleanField("В подборке", default=False)

    price = models.DecimalField("Цена", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_price = models.DecimalField("Цена со скидкой", max_digits=10, decimal_places=2, null=True, blank=True)

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


class Review(TimestampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="reviews", verbose_name="Курс")
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews", verbose_name="Пользователь"
    )
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


class Payment(TimestampedModel):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    STATUS_CHOICES = [
        (PENDING, "В ожидании"),
        (SUCCESS, "Успешно"),
        (FAILED, "Ошибка"),
    ]

    CARD = "card"
    KASPI = "kaspi"
    BANK_TRANSFER = "bank_transfer"
    TYPE_CHOICES = [
        (CARD, "Карта"),
        (KASPI, "Kaspi"),
        (BANK_TRANSFER, "Банковский перевод"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments", verbose_name="Пользователь")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="payments", verbose_name="Курс")
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("Статус", max_length=16, choices=STATUS_CHOICES, default=PENDING)
    type = models.CharField("Тип оплаты", max_length=20, choices=TYPE_CHOICES, default=KASPI)
    kaspi_invoice_id = models.CharField(
        "Kaspi invoice ID", max_length=255, null=True, blank=True, unique=True
    )
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


class ContactMessage(TimestampedModel):
    name = models.CharField("Имя", max_length=120)
    email = models.EmailField("Email")
    subject = models.CharField("Тема", max_length=200)
    message = models.TextField("Сообщение")
    is_processed = models.BooleanField("Обработано", default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Сообщение контактов"
        verbose_name_plural = "Сообщения контактов"

    def __str__(self):
        return f"{self.email}: {self.subject}"


try:
    from ckeditor_uploader.fields import RichTextUploadingField
    _RichField = RichTextUploadingField
except Exception:
    _RichField = models.TextField


class Article(TimestampedModel):
    DRAFT = "draft"
    PUBLISHED = "published"
    STATUS_CHOICES = [(DRAFT, "Черновик"), (PUBLISHED, "Опубликовано")]

    title = models.CharField("Заголовок", max_length=255)
    slug = models.SlugField("Слаг", max_length=255, unique=True, blank=True)
    excerpt = models.TextField("Краткое описание", blank=True)
    body = _RichField("Текст", default="Текст появится позже", blank=True)
    cover = models.ImageField("Обложка", upload_to="articles/", blank=True, null=True)
    view_count = models.PositiveIntegerField("Просмотры", default=0)

    seo_title = models.CharField("SEO Title", max_length=255, blank=True)
    seo_description = models.CharField("SEO Description", max_length=500, blank=True)
    seo_keywords = models.CharField("SEO Keywords", max_length=500, blank=True)
    seo_schema = models.TextField("SEO Schema (JSON-LD)", blank=True)

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
            self.slug = slugify(self.title)[:250] or f"article-{int(timezone.now().timestamp())}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("article_detail", args=[self.slug])


class Material(TimestampedModel):
    title = models.CharField("Название", max_length=200)
    slug = models.SlugField("Слаг", max_length=220, unique=True)
    description = models.TextField("Описание", blank=True)
    file = models.FileField("Файл", upload_to="materials/files/", blank=True, null=True)
    image = models.ImageField("Превью", upload_to="materials/images/", blank=True, null=True)
    is_public = models.BooleanField("Показывать на сайте", default=True)
    download_count = models.PositiveIntegerField("Скачивания", default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Материал"
        verbose_name_plural = "Материалы"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or f"material-{int(timezone.now().timestamp())}"
            self.slug = base
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("materials_list") + f"#{self.slug}"


# LMS модуль
class Quiz(TimestampedModel):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="quizzes")
    title = models.CharField("Название теста", max_length=255)
    passing_score = models.PositiveIntegerField("Проходной балл", default=70)
    time_limit = models.PositiveIntegerField("Лимит времени (мин)", null=True, blank=True)
    attempts_allowed = models.PositiveIntegerField("Попыток разрешено", default=1)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Тест"
        verbose_name_plural = "Тесты"
        ordering = ["lesson", "title"]

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"


class Question(TimestampedModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField("Вопрос")
    question_type = models.CharField("Тип вопроса", max_length=20, choices=[
        ('single', "Один вариант"), 
        ('multiple', "Несколько вариантов"),
        ('text', "Текстовый ответ")
    ], default='single')
    order = models.PositiveIntegerField("Порядок", default=1)
    points = models.PositiveIntegerField("Баллы", default=1)

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

    class Meta:
        verbose_name = "Домашнее задание"
        verbose_name_plural = "Домашние задания"
        ordering = ["course", "-due_date"]

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Submission(TimestampedModel):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="submissions")
    file = models.FileField("Файл работы", upload_to="submissions/", blank=True, null=True)
    text = models.TextField("Текст работы", blank=True)
    submitted_at = models.DateTimeField("Время отправки", auto_now_add=True)
    grade = models.PositiveIntegerField("Оценка", null=True, blank=True)
    feedback = models.TextField("Обратная связь", blank=True)

    class Meta:
        verbose_name = "Сданная работа"
        verbose_name_plural = "Сданные работы"
        constraints = [
            models.UniqueConstraint(fields=["assignment", "user"], name="uniq_submission_assignment_user"),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.assignment.title}"


class Certificate(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    certificate_id = models.CharField("ID сертификата", max_length=100, unique=True)
    issued_at = models.DateTimeField("Выдан", auto_now_add=True)
    pdf_file = models.FileField("PDF файл", upload_to="certificates/", blank=True, null=True)
    is_revoked = models.BooleanField("Аннулирован", default=False)

    class Meta:
        verbose_name = "Сертификат"
        verbose_name_plural = "Сертификаты"
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_certificate_user_course"),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.course.title}"


# CRM модуль
class Lead(TimestampedModel):
    email = models.EmailField("Email")
    name = models.CharField("Имя", max_length=120)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    source = models.CharField("Источник", max_length=100, default="website")
    status = models.CharField("Статус", max_length=20, choices=[
        ('new', "Новый"),
        ('contacted', "Связались"),
        ('qualified', "Квалифицирован"),
        ('converted', "Конвертирован")
    ], default='new')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name="assigned_leads")
    converted = models.BooleanField("Конвертирован", default=False)
    notes = models.TextField("Заметки", blank=True)

    class Meta:
        verbose_name = "Лид"
        verbose_name_plural = "Лиды"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.email}"


class Interaction(TimestampedModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="interactions")
    type = models.CharField("Тип взаимодействия", max_length=20, choices=[
        ('call', "Звонок"),
        ('email', "Email"),
        ('meeting', "Встреча"),
        ('message', "Сообщение")
    ])
    description = models.TextField("Описание")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interactions")
    result = models.CharField("Результат", max_length=200, blank=True)

    class Meta:
        verbose_name = "Взаимодействие"
        verbose_name_plural = "Взаимодействия"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.lead.name} - {self.type}"


class UserProfile(TimestampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField("Телефон", max_length=20, blank=True)
    city = models.CharField("Город", max_length=100, blank=True)
    balance = models.DecimalField("Баланс", max_digits=10, decimal_places=2, default=0)
    role = models.CharField("Роль", max_length=20, choices=[
        ('student', "Студент"),
        ('instructor', "Инструктор"),
        ('manager', "Менеджер"),
        ('admin', "Администратор")
    ], default='student')
    segment = models.CharField("Сегмент", max_length=50, blank=True)
    last_activity = models.DateTimeField("Последняя активность", null=True, blank=True)

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class Segment(TimestampedModel):
    name = models.CharField("Название", max_length=100)
    description = models.TextField("Описание", blank=True)
    conditions = models.JSONField("Условия", default=dict)
    users = models.ManyToManyField(User, related_name="segments", blank=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Сегмент"
        verbose_name_plural = "Сегменты"

    def __str__(self):
        return self.name


# Support модуль
class SupportTicket(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="support_tickets")
    subject = models.CharField("Тема", max_length=200)
    description = models.TextField("Описание проблемы")
    status = models.CharField("Статус", max_length=20, choices=[
        ('open', "Открыт"),
        ('in_progress', "В работе"),
        ('resolved', "Решен"),
        ('closed', "Закрыт")
    ], default='open')
    priority = models.CharField("Приоритет", max_length=20, choices=[
        ('low', "Низкий"),
        ('medium', "Средний"),
        ('high', "Высокий"),
        ('urgent', "Срочный")
    ], default='medium')
    category = models.CharField("Категория", max_length=50, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name="assigned_tickets")

    class Meta:
        verbose_name = "Тикет поддержки"
        verbose_name_plural = "Тикеты поддержки"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.subject}"


class FAQ(TimestampedModel):
    question = models.CharField("Вопрос", max_length=500)
    answer = models.TextField("Ответ")
    category = models.CharField("Категория", max_length=100)
    order = models.PositiveIntegerField("Порядок", default=1)
    is_active = models.BooleanField("Активен", default=True)
    view_count = models.PositiveIntegerField("Просмотры", default=0)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQ"
        ordering = ["category", "order"]

    def __str__(self):
        return self.question


# Billing модуль
class Subscription(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey('Plan', on_delete=models.CASCADE, related_name="subscriptions")
    status = models.CharField("Статус", max_length=20, choices=[
        ('active', "Активна"),
        ('canceled', "Отменена"),
        ('expired', "Истекла"),
        ('pending', "Ожидание")
    ], default='pending')
    start_date = models.DateTimeField("Начало")
    end_date = models.DateTimeField("Окончание")
    auto_renew = models.BooleanField("Автопродление", default=True)

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"


class Plan(TimestampedModel):
    name = models.CharField("Название", max_length=100)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField("Длительность (дни)")
    features = models.JSONField("Возможности", default=list)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Тарифный план"
        verbose_name_plural = "Тарифные планы"

    def __str__(self):
        return self.name


class Refund(TimestampedModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="refunds")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refunds")
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    reason = models.TextField("Причина")
    status = models.CharField("Статус", max_length=20, choices=[
        ('pending', "На рассмотрении"),
        ('approved', "Одобрен"),
        ('rejected', "Отклонен"),
        ('processed', "Обработан")
    ], default='pending')

    class Meta:
        verbose_name = "Возврат"
        verbose_name_plural = "Возвраты"

    def __str__(self):
        return f"{self.user.username} - {self.amount}"


# Marketing модуль
class Mailing(TimestampedModel):
    subject = models.CharField("Тема", max_length=200)
    message = models.TextField("Сообщение")
    channel = models.CharField("Канал", max_length=20, choices=[
        ('email', "Email"),
        ('telegram', "Telegram"),
        ('push', "Push-уведомление")
    ], default='email')
    segment = models.ForeignKey(Segment, on_delete=models.CASCADE, related_name="mailings")
    status = models.CharField("Статус", max_length=20, choices=[
        ('draft', "Черновик"),
        ('scheduled', "Запланирована"),
        ('sent', "Отправлена"),
        ('canceled', "Отменена")
    ], default='draft')
    sent_at = models.DateTimeField("Отправлено", null=True, blank=True)
    sent = models.PositiveIntegerField("Отправлено", default=0)
    opens = models.PositiveIntegerField("Открытия", default=0)
    clicks = models.PositiveIntegerField("Клики", default=0)

    class Meta:
        verbose_name = "Рассылка"
        verbose_name_plural = "Рассылки"
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject

    @property
    def open_percentage(self):
        return round((self.opens / self.sent * 100), 2) if self.sent > 0 else 0