from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .forms import EmailAuthenticationForm
from . import views
from django.conf import settings
from django.conf.urls.static import static

# Безопасный webhook токен (генерируйте уникальный для продакшена)
KASPI_WEBHOOK_SECRET = 'your-secure-webhook-token'

urlpatterns = [
    # --- Админка ---
    path('admin/', admin.site.urls),

    # --- Главная и статические страницы ---
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('design-wireframe/', views.design_wireframe, name='design_wireframe'),

    # --- Курсы ---
    path('courses/', views.courses_list, name='courses_list'),
    path('course/<slug:slug>/', views.course_detail, name='course_detail'),
    path('course/<slug:slug>/enroll/', views.enroll_course, name='enroll_course'),
    path('course/<slug:slug>/review/', views.add_review, name='add_review'),
    path('course/<slug:slug>/wishlist/', views.toggle_wishlist, name='toggle_wishlist'),
    path('course/<slug:course_slug>/lesson/<slug:lesson_slug>/', views.lesson_detail, name='lesson_detail'),

    # --- Пользовательский кабинет ---
    path('my-courses/', views.my_courses, name='my_courses'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # --- Аутентификация ---
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=EmailAuthenticationForm
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),

    # --- Сброс пароля ---
    path('password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # --- Локализация ---
    path('i18n/', include('django.conf.urls.i18n')),

    # --- Безопасный Kaspi webhook ---
    path(f'payment/webhook/{KASPI_WEBHOOK_SECRET}/', views.kaspi_webhook, name='kaspi_webhook'),
]

# --- Статика и медиа только для DEBUG ---
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
