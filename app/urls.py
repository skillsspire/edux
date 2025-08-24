from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Главная страница
    path('', views.home, name='home'),

    # Курсы
    path('courses/', views.courses_list, name='courses_list'),
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
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]