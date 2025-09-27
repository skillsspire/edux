from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from .forms import EmailAuthenticationForm
from . import views

urlpatterns = [
    # --- Админка ---
    path("admin/", admin.site.urls),

    # --- Главная и статические страницы ---
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("design-wireframe/", views.design_wireframe, name="design_wireframe"),

    # --- Курсы ---
    path("courses/", views.courses_list, name="courses_list"),
    path("course/<slug:slug>/", views.course_detail, name="course_detail"),
    path("course/<slug:slug>/enroll/", views.enroll_course, name="enroll_course"),
    path("course/<slug:slug>/review/", views.add_review, name="add_review"),
    path("course/<slug:slug>/wishlist/", views.toggle_wishlist, name="toggle_wishlist"),
    path(
        "course/<slug:course_slug>/lesson/<slug:lesson_slug>/",
        views.lesson_detail,
        name="lesson_detail",
    ),

    # --- Оплата ---
    path("course/<slug:slug>/pay/", views.create_payment, name="create_payment"),
    path("course/<slug:slug>/pay/claim/", views.payment_claim, name="payment_claim"),
    path("course/<slug:slug>/pay/thanks/", views.payment_thanks, name="payment_thanks"),

    # --- Пользовательский кабинет ---
    path("my-courses/", views.my_courses, name="my_courses"),
    path("dashboard/", views.dashboard, name="dashboard"),

    # --- Аутентификация ---
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=EmailAuthenticationForm,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),

    # --- Сброс пароля ---
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html"
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # --- Локализация ---
    path("i18n/", include("django.conf.urls.i18n")),

    # --- Kaspi webhook ---
    path(
        f"payment/webhook/{getattr(settings, 'KASPI_WEBHOOK_SECRET', 'dev-secret')}/",
        views.kaspi_webhook,
        name="kaspi_webhook",
    ),
]

# --- Статика и медиа только для DEBUG ---
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
