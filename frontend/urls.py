from django.urls import path

from . import views

app_name = "frontend"

urlpatterns = [
    path("", views.home_page, name="home"),
    path("kirish/", views.login_page, name="login"),
    path("royxatdan-otish/", views.register_page, name="register"),
    path("tasdiqlash/", views.verify_page, name="verify"),
    path("parolni-tiklash/", views.password_reset_page, name="password-reset"),
    path("kabinet/", views.dashboard_page, name="dashboard"),

    # Ommaviy sayt / shaxsiy kabinet
    path("dokon/", views.shop_page, name="shop"),
    path("dokon/<slug:slug>/", views.product_detail_page, name="product-detail"),
    path("savat/", views.cart_page, name="cart"),
    path("kurslar/", views.courses_page, name="courses"),
    path("kurslar/<slug:slug>/", views.course_detail_page, name="course-detail"),
    path("kurslar/<slug:slug>/dars/<int:lesson_id>/", views.lesson_page, name="lesson"),
    path("liderlar/", views.leaderboard_page, name="leaderboard"),
    path("premium/", views.premium_page, name="premium"),
    path("mini-app/", views.miniapp_page, name="miniapp"),
]
