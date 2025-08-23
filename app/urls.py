from django.contrib import admin
from django.urls import path, include
from app import views
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),

    # Auth
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    #path('signup/', views.signup, name='signup'),  # если сделаем кастомную регистрацию
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),

    # Courses
    path('courses/', views.courses_list, name='courses_list'),
    path('courses/<slug:course_slug>/', views.course_detail, name='course_detail'),
    path('courses/<slug:course_slug>/enroll/', views.enroll_course, name='enroll_course'),

    # Lessons
    path('courses/<slug:course_slug>/lessons/<slug:lesson_slug>/', views.lesson_detail, name='lesson_detail'),
    path('enrollment/<int:enrollment_id>/lesson/<int:lesson_id>/complete/', views.mark_lesson_complete, name='mark_lesson_complete'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
]
