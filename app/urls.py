from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from app.views import home, about, contact, signup, courses_list, course_detail, enroll_course, lesson_detail, mark_lesson_complete, dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('about/', about, name='about'),
    path('contact/', contact, name='contact'),

    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('signup/', signup, name='signup'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),

    path('courses/', courses_list, name='courses_list'),
    path('courses/<slug:course_slug>/enroll/', enroll_course, name='enroll_course'),
    path('courses/<slug:course_slug>/lessons/<slug:lesson_slug>/', lesson_detail, name='lesson_detail'),
    path('courses/<slug:course_slug>/lessons/<slug:lesson_slug>/complete/', mark_lesson_complete, name='mark_lesson_complete'),
    path('courses/<slug:course_slug>/', course_detail, name='course_detail'),

    path('dashboard/', dashboard, name='dashboard'),

    path('i18n/', include('django.conf.urls.i18n')),
]