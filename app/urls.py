from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    # auth
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),

    # courses
    path("courses/", views.courses_list, name="courses_list"),
    path("course/<slug:slug>/", views.course_detail, name="course_detail"),
    path("course/<slug:slug>/enroll/", views.enroll_course, name="enroll_course"),
    path("course/<slug:slug>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("course/<slug:slug>/review/add/", views.add_review, name="add_review"),

    # lessons
    path("course/<slug:course_slug>/lesson/<slug:lesson_slug>/", views.lesson_detail, name="lesson_detail"),

    # payments
    path("course/<slug:slug>/payment/", views.create_payment, name="create_payment"),
    path("course/<slug:slug>/payment/claim/", views.payment_claim, name="payment_claim"),
    path("course/<slug:slug>/payment/thanks/", views.payment_thanks, name="payment_thanks"),
    path("kaspi/webhook/", views.kaspi_webhook, name="kaspi_webhook"),

    # articles
    path("articles/", views.articles_list, name="articles_list"),
    path("article/<slug:slug>/", views.article_detail, name="article_detail"),

    # materials
    path("materials/", views.materials_list, name="materials_list"),

    # user area
    path("my-courses/", views.my_courses, name="my_courses"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/settings/", views.profile_settings, name="profile_settings"),

    # static pages
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("design/", views.design_wireframe, name="design_wireframe"),
]
