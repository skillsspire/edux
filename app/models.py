from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import DatabaseError
from django.templatetags.static import static

DEFAULT_COURSE_IMAGE = 'img/courses/default.jpg'
DEFAULT_AVATAR_IMAGE = 'img/avatar-default.png'

# Supabase project ID - должен совпадать с настройками
SUPABASE_PROJECT_ID = "pyttzlcuxyfkhrwggrwi"
SUPABASE_BUCKET_NAME = "media"


def safe_file_url(file_field, default_path):
    try:
        if file_field and getattr(file_field, 'url', None):
            return file_field.url
    except Exception:
        pass
    return static(default_path)


def get_supabase_file_url(file_field, default_path):
    """Возвращает правильный URL для файла в Supabase Storage"""
    if file_field and file_field.name:
        # Убираем имя bucket'а из пути, так как он уже указан в URL
        filename = file_field.name.replace(f'{SUPABASE_BUCKET_NAME}/', '')
        return f"https://{SUPABASE_PROJECT_ID}.supabase.co/storage/v1/object/public/{SUPABASE_BUCKET_NAME}/{filename}"
    return static(default_path)


User.add_to_class(
    'is_instructor',
    property(lambda self: hasattr(self, 'instructor_profile') and getattr(self.instructor_profile, 'is_approved', False))
)


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название")
    slug = models.SlugField(unique=True, blank=True, verbose_name="URL")
    description = models.TextField(blank=True, verbose_name="Описание")
    icon = models.CharField(max_length=50, blank=True, verbose_name="Иконка")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('courses_by_category', kwargs={'slug': self.slug})


class InstructorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instructor_profile')
    bio = models.TextField(verbose_name="Биография")
    avatar = models.ImageField(upload_to='instructors/avatars/', blank=True, null=True, verbose_name="Аватар")
    specialization = models.CharField(max_length=200, verbose_name="Специализация")
    experience = models.PositiveIntegerField(default=0, verbose_name="Опыт работы (лет)")
    website = models.URLField(blank=True, verbose_name="Вебсайт")
    linkedin = models.URLField(blank=True, verbose_name="LinkedIn")
    twitter = models.URLField(blank=True, verbose_name="Twitter")
    is_approved = models.BooleanField(default=False, verbose_name="Подтвержден")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Профиль инструктора"
        verbose_name_plural = "Профили инструкторов"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    @property
    def courses_count(self):
        return self.user.courses_created.count()

    @property
    def avatar_safe_url(self):
        return safe_file_url(self.avatar, DEFAULT_AVATAR_IMAGE)

    @property
    def avatar_supabase_url(self):
        """Возвращает правильный URL аватара из Supabase"""
        return get_supabase_file_url(self.avatar, DEFAULT_AVATAR_IMAGE)

    @property
    def display_avatar_url(self):
        """Основной метод для отображения аватара"""
        return self.avatar_supabase_url or self.avatar_safe_url


class Course(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Начинающий'),
        ('intermediate', 'Средний'),
        ('advanced', 'Продвинутый'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('review', 'На проверке'),
        ('published', 'Опубликован'),
    ]

    title = models.CharField(max_length=200, verbose_name="Название")
    slug = models.SlugField(unique=True, blank=True, verbose_name="URL")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='courses', verbose_name="Категория")
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_created', null=True, blank=True)
    short_description = models.TextField(verbose_name="Краткое описание")
    description = models.TextField(verbose_name="Полное описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Цена")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Цена со скидкой")
    duration_hours = models.PositiveIntegerField(default=0, verbose_name="Продолжительность (часы)")
    image = models.ImageField(upload_to='courses/images/', blank=True, null=True, verbose_name="Изображение")
    thumbnail = models.ImageField(upload_to='courses/thumbnails/', blank=True, null=True, verbose_name="Миниатюра")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner', verbose_name="Уровень")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Статус")
    is_featured = models.BooleanField(default=False, verbose_name="Рекомендуемый")
    is_popular = models.BooleanField(default=False, verbose_name="Популярный")
    students = models.ManyToManyField(User, related_name='enrolled_courses', blank=True, verbose_name="Студенты")
    requirements = models.TextField(blank=True, verbose_name="Требования")
    what_you_learn = models.TextField(blank=True, verbose_name="Чему научитесь")
    language = models.CharField(max_length=50, default="Русский", verbose_name="Язык")
    certificate = models.BooleanField(default=True, verbose_name="Сертификат")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('course_detail', kwargs={'slug': self.slug})

    @property
    def has_discount(self):
        return bool(self.discount_price is not None and self.price and self.price > 0 and self.discount_price < self.price)

    @property
    def discount_percent(self):
        if self.has_discount:
            pct = int((1 - (float(self.discount_price) / float(self.price))) * 100)
            return max(0, min(100, pct))
        return None

    @property
    def lessons_count(self):
        return self.modules.filter(is_active=True).aggregate(total=models.Count('lessons'))['total'] or 0

    @property
    def students_count(self):
        return self.students.count()

    @property
    def average_rating(self):
        try:
            qs = self.reviews.filter(is_active=True)
            if qs.exists():
                return round(qs.aggregate(models.Avg('rating'))['rating__avg'], 1)
        except DatabaseError:
            pass
        return 4.5

    @property
    def rating(self):
        return self.average_rating

    @property
    def reviews_count(self):
        try:
            return self.reviews.filter(is_active=True).count()
        except DatabaseError:
        return 0

    @property
    def image_safe_url(self):
        return safe_file_url(self.image, DEFAULT_COURSE_IMAGE)

    @property
    def thumbnail_safe_url(self):
        return safe_file_url(self.thumbnail, DEFAULT_COURSE_IMAGE)

    @property
    def image_supabase_url(self):
        """Возвращает правильный URL изображения из Supabase"""
        return get_supabase_file_url(self.image, DEFAULT_COURSE_IMAGE)

    @property
    def thumbnail_supabase_url(self):
        """Возвращает правильный URL миниатюры из Supabase"""
        return get_supabase_file_url(self.thumbnail, DEFAULT_COURSE_IMAGE)

    @property
    def display_image_url(self):
        """Основной метод для отображения изображения курса"""
        # Приоритет: Supabase thumbnail -> Supabase image -> безопасные URL -> дефолтное изображение
        return (
            self.thumbnail_supabase_url or 
            self.image_supabase_url or 
            self.thumbnail_safe_url or 
            self.image_safe_url
        )

    @property
    def duration_display(self):
        """Отформатированное отображение длительности"""
        if self.duration_hours == 0:
            return "Не указано"
        elif self.duration_hours == 1:
            return "1 час"
        elif self.duration_hours < 5:
            return f"{self.duration_hours} часа"
        else:
            return f"{self.duration_hours} часов"


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Модуль"
        verbose_name_plural = "Модули"
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Lesson(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200, verbose_name="Название")
    slug = models.SlugField(blank=True, verbose_name="URL")
    content = models.TextField(verbose_name="Содержание")
    video_url = models.URLField(blank=True, verbose_name="Видео URL")
    duration_minutes = models.PositiveIntegerField(default=0, verbose_name="Длительность (мин.)")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_free = models.BooleanField(default=False, verbose_name="Бесплатный")
    resources = models.FileField(upload_to='lessons/resources/', blank=True, null=True, verbose_name="Ресурсы")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['module', 'slug'], name='uq_lesson_module_slug'),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            'lesson_detail',
            kwargs={'course_slug': self.module.course.slug, 'lesson_slug': self.slug}
        )

    @property
    def duration_display(self):
        """Отформатированное отображение длительности урока"""
        if self.duration_minutes == 0:
            return "Не указано"
        elif self.duration_minutes < 60:
            return f"{self.duration_minutes} мин."
        else:
            hours = self.duration_minutes // 60
            minutes = self.duration_minutes % 60
            if minutes == 0:
                return f"{hours} ч."
            else:
                return f"{hours} ч. {minutes} мин."


class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Запись на курс"
        verbose_name_plural = "Записи на курсы"
        constraints = [
            models.UniqueConstraint(fields=['user', 'course'], name='uq_enrollment_user_course'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.course.title}"


class Review(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    name = models.CharField(max_length=100, verbose_name="Имя")
    position = models.CharField(max_length=200, blank=True, verbose_name="Должность/Род занятий")
    age = models.PositiveIntegerField(null=True, blank=True, verbose_name="Возраст")
    photo = models.ImageField(upload_to='reviews/photos/', blank=True, null=True, verbose_name="Фото")
    rating = models.DecimalField(
        max_digits=2, decimal_places=1,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
        verbose_name="Рейтинг"
    )
    comment = models.TextField(verbose_name="Комментарий")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    def __str__(self):
        return f"{self.name} - {self.course.title} - {self.rating}"

    @property
    def photo_supabase_url(self):
        """Возвращает правильный URL фото из Supabase"""
        return get_supabase_file_url(self.photo, DEFAULT_AVATAR_IMAGE)


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        constraints = [
            models.UniqueConstraint(fields=['user', 'course'], name='uq_wishlist_user_course'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.course.title}"


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('success', 'Успешно'),
        ('failed', 'Неудачно'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма")
    kaspi_invoice_id = models.CharField(max_length=100, unique=True, null=True, blank=True, verbose_name="ID платежа Kaspi")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"
        ordering = ['-created']

    def __str__(self):
        return f"{self.user.username} - {self.course.title} - {self.amount} - {self.status}"


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.user.username} - {self.start_date.date()}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Контактное сообщение"
        verbose_name_plural = "Контактные сообщения"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.subject}"


class LessonProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress')
    is_completed = models.BooleanField(default=False)
    percent = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Прогресс по уроку"
        verbose_name_plural = "Прогресс по урокам"
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'lesson'], name='uq_lessonprogress_user_lesson'),
        ]

    def __str__(self):
        return f'{self.user} · {self.lesson} · {self.percent}%'