from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .forms import EmailAuthenticationForm
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),  # ← ДОБАВЬТЕ ЭТУ СТРОЧКУ
    path('', views.home, name='home'),
    path('courses/', views.courses_list, name='course_list'),
    path('course/<slug:slug>/', views.course_detail, name='course_detail'),
    path('course/<slug:slug>/enroll/', views.enroll_course, name='enroll_course'),
    path('course/<slug:slug>/review/', views.add_review, name='add_review'),
    path('course/<slug:slug>/wishlist/', views.toggle_wishlist, name='toggle_wishlist'),
    path('course/<slug:course_slug>/lesson/<slug:lesson_slug>/', views.lesson_detail, name='lesson_detail'),

    # Пользовательские страницы
    path('my-courses/', views.my_courses, name='my_courses'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Статические страницы
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),

    # Аутентификация
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=EmailAuthenticationForm  # используйте кастомную форму
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),

    # Язык - добавьте эту строку
    path('i18n/', include('django.conf.urls.i18n')),

    # Сброс пароля (опционально)
    path('password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]