import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем .env
load_dotenv(os.path.join(BASE_DIR, '.env'))

RECAPTCHA_PUBLIC_KEY = os.environ.get("RECAPTCHA_PUBLIC_KEY")
RECAPTCHA_PRIVATE_KEY = os.environ.get("RECAPTCHA_PRIVATE_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-secret")
DEBUG = os.environ.get("DEBUG", "False") == "True"

if DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

CSRF_TRUSTED_ORIGINS = [
    "https://www.skillsspire.com",
    "https://skillsspire.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    if RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    origin = f"https://{RENDER_EXTERNAL_HOSTNAME}"
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

KASPI_WEBHOOK_SECRET = os.environ.get("KASPI_WEBHOOK_SECRET", "dev-secret")
KASPI_PAYMENT_URL = os.environ.get("KASPI_PAYMENT_URL", "https://pay.kaspi.kz/pay/fhljzakr")
KASPI_SECRET = os.environ.get("KASPI_SECRET", "dev-secret")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_DOMAIN = None
SESSION_COOKIE_DOMAIN = None
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_REFERRER_POLICY = "same-origin"

DJANGO_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "phonenumber_field",
    "ckeditor",
    "widget_tweaks",
    "storages",
]

LOCAL_APPS = [
    "app.apps.CoreConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates", BASE_DIR / "app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "app.context.kaspi",
            ],
        },
    },
]

WSGI_APPLICATION = "app.wsgi.application"

USE_PGBOUNCER = os.environ.get("DB_PGBOUNCER", "False") == "True"
CONN_MAX_AGE_VALUE = 0 if USE_PGBOUNCER else 600

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    db_cfg = dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=CONN_MAX_AGE_VALUE,
        ssl_require=True,
    )
    db_cfg["CONN_HEALTH_CHECKS"] = True
    DATABASES = {"default": db_cfg}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

SESSION_ENGINE = "django.contrib.sessions.backends.db"
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = [
    "app.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/login/"

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True
LANGUAGES = [
    ("en", "English"),
    ("ru", "Русский"),
    ("kz", "Қазақша"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "app" / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_MAX_AGE = 60 if DEBUG else 60 * 60 * 24 * 365

if DEBUG:
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
else:
    SUPABASE_PROJECT_ID = "pyttzlcuxyfkhrwggrwi"
    SUPABASE_BUCKET_NAME = os.getenv("SUPABASE_BUCKET", "media")

    MEDIA_URL = f"https://{SUPABASE_PROJECT_ID}.supabase.co/storage/v1/object/public/{SUPABASE_BUCKET_NAME}/"
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

    AWS_ACCESS_KEY_ID = os.getenv("SUPABASE_ACCESS_KEY")
    AWS_SECRET_ACCESS_KEY = os.getenv("SUPABASE_SECRET_KEY")
    AWS_STORAGE_BUCKET_NAME = SUPABASE_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = f"https://{SUPABASE_PROJECT_ID}.supabase.co/storage/v1/s3"

    AWS_S3_REGION_NAME = "us-east-1"
    AWS_S3_ADDRESSING_STYLE = "path"
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT") or 587)
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "SkillsSpire <noreply@skillsspire.com>")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "30"))

PHONENUMBER_DEFAULT_REGION = "KZ"
PHONENUMBER_DEFAULT_FORMAT = "INTERNATIONAL"

SILENCED_SYSTEM_CHECKS = ["ckeditor.W001"]

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": os.getenv("DB_LOG_LEVEL", "WARNING")},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

JAZZMIN_SETTINGS = {
    "site_title": "SkillsSpire Admin",
    "site_header": "SkillsSpire",
    "welcome_sign": "Добро пожаловать в панель управления SkillsSpire",
    "site_brand": "SkillsSpire",
    "site_logo": "app/static/img/logo_skillsspire.png",
    "copyright": "© 2025 SkillsSpire",
    "theme": "cosmo",
    "show_ui_builder": True,
    "custom_css": "css/admin_custom.css" if DEBUG else None,
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [
        "app.Course", "app.Module", "app.Lesson",
        "app.Enrollment", "app.Payment", "app.Review",
        "auth.User", "auth.Group",
    ],
    "icons": {
        "auth.User": "fas fa-user",
        "auth.Group": "fas fa-users",
        "app.Category": "fas fa-folder-tree",
        "app.Course": "fas fa-graduation-cap",
        "app.Module": "fas fa-layer-group",
        "app.Lesson": "fas fa-play-circle",
        "app.LessonProgress": "fas fa-tasks",
        "app.Enrollment": "fas fa-user-graduate",
        "app.Payment": "fas fa-credit-card",
        "app.InstructorProfile": "fas fa-chalkboard-teacher",
        "app.Review": "fas fa-star",
        "app.Wishlist": "fas fa-heart",
        "app.ContactMessage": "fas fa-envelope",
        "app.Article": "fas fa-newspaper",
        "app.Material": "fas fa-book",
        "app.Quiz": "fas fa-question-circle",
        "app.Question": "fas fa-question",
        "app.Answer": "fas fa-check-circle",
        "app.Assignment": "fas fa-tasks",
        "app.Submission": "fas fa-file-upload",
        "app.Certificate": "fas fa-certificate",
        "app.Lead": "fas fa-user-plus",
        "app.Interaction": "fas fa-comments",
        "app.UserProfile": "fas fa-user-circle",
        "app.Segment": "fas fa-users",
        "app.SupportTicket": "fas fa-ticket-alt",
        "app.FAQ": "fas fa-question-circle",
        "app.Subscription": "fas fa-calendar-alt",
        "app.Plan": "fas fa-cube",
        "app.Refund": "fas fa-undo",
        "app.Mailing": "fas fa-envelope-open-text",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "use_google_fonts_cdn": True,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },
}
