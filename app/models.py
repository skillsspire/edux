from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import DatabaseError
from django.templatetags.static import static

DEFAULT_COURSE_IMAGE = 'img/courses/default.jpg'
DEFAULT_AVATAR_IMAGE = 'img/avatar-default.png'


def safe_file_url(file_field, default_path):
    try:
        if file_field and getattr(file_field, 'url', None):
            return file_field.url
    except Exception:
        pass
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
