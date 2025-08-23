from django.urls import path
from . import views
from django.contrib.auth import views as auth_views # Для использования стандартных представлений аутентификации

urlpatterns = [
    # Главная страница
    path('', views.home, name='home'),
    # Страницы аутентификации (Django предоставляет их из коробки, нам нужны только шаблоны)
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    #path('signup/', views.signup, name='signup'), # Это представление нам нужно будет создать позже
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset.html'), name='password_reset'),
    # Каталог и детали курса
    path('courses/', views.courses_list, name='courses_list'),
    path('courses/<slug:course_slug>/', views.course_detail, name='course_detail'),
    path('courses/<int:course_id>/enroll/', views.enroll_course, name='enroll_course'),
    # Уроки
    path('courses/<slug:course_slug>/lessons/<slug:lesson_slug>/', views.lesson_detail, name='lesson_detail'),
    path('enrollment/<int:enrollment_id>/lesson/<int:lesson_id>/complete/', views.mark_lesson_complete, name='mark_lesson_complete'),
    # Личный кабинет
    path('dashboard/', views.dashboard, name='dashboard'),
]