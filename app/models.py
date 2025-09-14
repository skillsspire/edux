from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import DatabaseError
from django.templatetags.static import static


# ===== Сервисные хелперы =====
DEFAULT_COURSE_IMAGE = 'img/courses/default.jpg'
DEFAULT_AVATAR_IMAGE = 'img/avatar-default.png'


def safe_file_url(file_field, default_path):
    """
    Безопасно возвращает .url даже если файл не прикреплён.
    Не бросает ValueError в шаблоне.
    """
    try:
        if file_field and getattr(file_field, 'url', None):
            return file_field.url
    except Exception:
        pass
    return static(default_path)


# Добавляем свойство к User: является ли инструктором
User.add_to_class(
    'is_instructor',
    property(lambda self: hasattr(self, 'instructor_profile') and getattr(self.instructor_profile, 'is_approved', False))
)


# ==========================
# Категории курсов
# ==========================
class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название")
    slug = models.SlugField(unique=True, verbose_name="URL")
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


# ==========================
# Профиль инструктора
# ==========================
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


# ==========================
# Курсы
# ==========================
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
    slug = models.SlugField(unique=True, verbose_name="URL")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='courses', verbose_name="Категория")
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_created', null=True, blank=True)
    short_description = models.TextField(verbose_name="Краткое описание")
    description = models.TextField(verbose_name="Полное описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Цена")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Цена со скидкой")
    duration = models.CharField(max_length=50, verbose_name="Продолжительность")
    image = models.ImageField(upload_to='courses/images/', blank=True, null=True, verbose_name="Изображение")
    thumbnail = models.ImageField(upload_to='courses/thumbnails/', blank=True, null=True, verbose_name="Миниатюра")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner', verbose_name="Уровень")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Статус")
    is_featured = models.BooleanField(default=False, verbose_name="Рекомендуемый")
    is_popular = models.BooleanField(default=False, verbose_name="Популярный")  # используется в шаблонах
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

    # ---- свойства для шаблонов ----
    @property
    def has_discount(self):
        return bool(self.discount_price and self.price and self.price > 0)

    @property
    def discount_percent(self):
        if self.has_discount:
            return int((1 - (float(self.discount_price) / float(self.price))) * 100)
        return None

    @property
    def lessons_count(self):
        return self.lessons.filter(is_active=True).count()

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

    # чтобы {{ course.rating }} работал так же, как average_rating
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


# ==========================
# Модули и уроки
# ==========================
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
    slug = models.SlugField(verbose_name="URL")
    content = models.TextField(verbose_name="Содержание")
    video_url = models.URLField(blank=True, verbose_name="Видео URL")
    duration = models.CharField(max_length=50, blank=True, verbose_name="Продолжительность")
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
        unique_together = ['module', 'slug']

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


# ==========================
# Запись, Отзывы, Избранное, Платежи, Подписки, Контакты
# ==========================
class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Запись на курс"
        verbose_name_plural = "Записи на курсы"
        unique_together = ['user', 'course']

    def __str__(self):
        return f"{self.user.username} - {self.course.title}"


class Review(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Рейтинг"
    )
    comment = models.TextField(verbose_name="Комментарий")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        unique_together = ['course', 'user']
    def __str__(self):
        return f"{self.user.username} - {self.course.title} - {self.rating}"


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        unique_together = ['user', 'course']

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


# ==========================
# Прогресс по урокам (для дашборда)
# ==========================
class LessonProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress')
    is_completed = models.BooleanField(default=False)
    percent = models.PositiveSmallIntegerField(default=0)  # 0..100
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Прогресс по уроку"
        verbose_name_plural = "Прогресс по урокам"
        unique_together = ('user', 'lesson')
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.user} · {self.lesson} · {self.percent}%'
