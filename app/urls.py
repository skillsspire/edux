# app/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from .forms import EmailAuthenticationForm
from . import views

urlpatterns = [
    # 1️⃣ АДМИНКА (стандартная) — точка управления
    path("admin/", admin.site.urls),
    
    # 2️⃣ ПУБЛИЧНЫЕ СТРАНИЦЫ
    path("", views.home, name="home"),
    path("about/", TemplateView.as_view(template_name="about.html"), name="about"),
    path("contact/", views.contact, name="contact"),
    path("pricing/", TemplateView.as_view(template_name="pricing.html"), name="pricing"),
    
    # 3️⃣ КАТАЛОГ (единая точка входа)
    path("catalog/", views.catalog, name="catalog"),
    path("courses/", views.courses_list, name="courses_list"),
    path("courses/<slug:slug>/", views.course_detail, name="course_detail"),
    path("categories/<slug:slug>/", views.category_detail, name="category_detail"),
    
    # 4️⃣ ОБУЧЕНИЕ (LMS — отдельный контекст)
    path("learn/", views.learning_dashboard, name="learning_dashboard"),
    path("learn/<slug:course_slug>/", views.course_learn, name="course_learn"),
    path("learn/<slug:course_slug>/<slug:lesson_slug>/", views.lesson_view, name="lesson_view"),
    path("api/progress/", views.update_progress, name="update_progress"),
    
    # 5️⃣ ИНСТРУКТОР (отдельная панель — НЕ Django Admin)
    path("instructor/", views.instructor_dashboard, name="instructor_dashboard"),
    path("instructor/courses/", views.instructor_courses, name="instructor_courses"),
    path("instructor/courses/<slug:slug>/", views.instructor_course_detail, name="instructor_course_detail"),
    path("instructor/analytics/", views.instructor_analytics, name="instructor_analytics"),
    path("instructor/students/", views.instructor_students, name="instructor_students"),
    
    # 6️⃣ АУТЕНТИФИКАЦИЯ (минимально)
    path("login/", auth_views.LoginView.as_view(
        template_name="auth/login.html",
        authentication_form=EmailAuthenticationForm,
        redirect_authenticated_user=True
    ), name="login"),
    
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("account/", views.account_settings, name="account_settings"),
    
    # 7️⃣ ОПЛАТА (единый flow)
    path("checkout/<slug:slug>/", views.checkout, name="checkout"),
    path("checkout/<slug:slug>/confirm/", views.checkout_confirm, name="checkout_confirm"),
    path("payment/webhook/", views.payment_webhook, name="payment_webhook"),
    
    # 8️⃣ API (только по необходимости)
    path("api/courses/", views.api_courses, name="api_courses"),
    path("api/enroll/", views.api_enroll, name="api_enroll"),
    path("api/reviews/", views.api_reviews, name="api_reviews"),
    
    # 9️⃣ CRM (внутреннее — только для staff)
    path("crm/", views.crm_dashboard, name="crm_dashboard"),
    path("crm/leads/", views.crm_leads, name="crm_leads"),
    path("crm/payments/", views.crm_payments, name="crm_payments"),
    
    # 🔟 СЛУЖЕБНЫЕ
    path("health/", views.health_check, name="health_check"),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("sitemap.xml", views.sitemap, name="sitemap"),
]

# Медиа и статика только в DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# 404 и 500 (продакшен)
handler404 = "app.views.handler404"
handler500 = "app.views.handler500"