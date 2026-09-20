from django.urls import path

from . import (
    views_auth,
    views_billing,
    views_content,
    views_courses,
    views_dashboard,
    views_shop,
    views_users,
)

app_name = "panel"

urlpatterns = [
    # Kirish
    path("login/", views_auth.panel_login, name="login"),
    path("logout/", views_auth.panel_logout, name="logout"),
    path("theme/", views_auth.set_theme, name="set_theme"),
    path("til/<str:code>/", views_auth.set_language, name="set_language"),

    # Dashboard va statistika
    path("", views_dashboard.dashboard, name="dashboard"),
    path("statistika/", views_dashboard.statistics, name="statistics"),
    path("jurnal/", views_content.activity_log, name="activity"),

    # Foydalanuvchilar
    path("foydalanuvchilar/", views_users.user_list, name="user_list"),
    path("foydalanuvchilar/<int:pk>/", views_users.user_detail, name="user_detail"),
    path("foydalanuvchilar/<int:pk>/tahrir/", views_users.user_edit, name="user_edit"),
    path("foydalanuvchilar/<int:pk>/blok/", views_users.user_toggle_block, name="user_block"),
    path("foydalanuvchilar/<int:pk>/ochirish/", views_users.user_delete, name="user_delete"),

    # Adminlar
    path("adminlar/", views_users.admin_list, name="admin_list"),
    path("adminlar/yangi/", views_users.admin_form, name="admin_create"),
    path("adminlar/<int:pk>/", views_users.admin_form, name="admin_edit"),
    path("adminlar/<int:pk>/ochirish/", views_users.admin_delete, name="admin_delete"),

    # Kurs kategoriyalari
    path("kategoriyalar/", views_courses.category_list, name="category_list"),
    path("kategoriyalar/yangi/", views_courses.category_form, name="category_create"),
    path("kategoriyalar/<int:pk>/", views_courses.category_form, name="category_edit"),
    path("kategoriyalar/<int:pk>/ochirish/", views_courses.category_delete, name="category_delete"),

    # Kurslar
    path("kurslar/", views_courses.course_list, name="course_list"),
    path("kurslar/yangi/", views_courses.course_form, name="course_create"),
    path("kurslar/<int:pk>/tahrir/", views_courses.course_form, name="course_edit"),
    path("kurslar/<int:pk>/", views_courses.course_content, name="course_content"),
    path("kurslar/<int:pk>/ochirish/", views_courses.course_delete, name="course_delete"),
    path("kurslar/<int:pk>/holat/", views_courses.course_toggle, name="course_toggle"),

    # Modullar
    path("kurslar/<int:course_pk>/modul/yangi/", views_courses.module_form, name="module_create"),
    path("kurslar/<int:course_pk>/modul/<int:pk>/", views_courses.module_form, name="module_edit"),
    path("kurslar/<int:course_pk>/modul/<int:pk>/ochirish/", views_courses.module_delete, name="module_delete"),

    # Darslar
    path("darslar/", views_courses.lesson_list, name="lesson_list"),
    path("kurslar/<int:course_pk>/dars/yangi/", views_courses.lesson_form, name="lesson_create"),
    path("kurslar/<int:course_pk>/dars/<int:pk>/", views_courses.lesson_form, name="lesson_edit"),
    path("kurslar/<int:course_pk>/dars/<int:pk>/ochirish/", views_courses.lesson_delete, name="lesson_delete"),
    path("kurslar/<int:course_pk>/dars/<int:pk>/holat/", views_courses.lesson_toggle, name="lesson_toggle"),
    path("fayl/<int:pk>/ochirish/", views_courses.attachment_delete, name="attachment_delete"),
    path("kurslar/<int:course_pk>/dars/<int:pk>/test/", views_courses.quiz_manage, name="quiz_manage"),
    path("kurslar/<int:course_pk>/dars/<int:pk>/test/<int:question_pk>/ochirish/",
         views_courses.quiz_question_delete, name="quiz_question_delete"),

    # Do'kon
    path("dokon/", views_shop.product_list, name="product_list"),
    path("dokon/yangi/", views_shop.product_form, name="product_create"),
    path("dokon/<int:pk>/", views_shop.product_form, name="product_edit"),
    path("dokon/<int:pk>/ochirish/", views_shop.product_delete, name="product_delete"),
    path("dokon/<int:pk>/holat/", views_shop.product_toggle, name="product_toggle"),
    path("dokon-kategoriya/", views_shop.shop_category_list, name="shop_category_list"),
    path("dokon-kategoriya/yangi/", views_shop.shop_category_form, name="shop_category_create"),
    path("dokon-kategoriya/<int:pk>/", views_shop.shop_category_form, name="shop_category_edit"),
    path("dokon-kategoriya/<int:pk>/ochirish/", views_shop.shop_category_delete, name="shop_category_delete"),
    path("buyurtmalar/", views_shop.order_list, name="order_list"),
    path("buyurtmalar/<int:pk>/", views_shop.order_detail, name="order_detail"),
    path("buyurtmalar/<int:pk>/ochirish/", views_shop.order_delete, name="order_delete"),

    # Premium
    path("premium/", views_billing.plan_list, name="plan_list"),
    path("premium/yangi/", views_billing.plan_form, name="plan_create"),
    path("premium/<int:pk>/", views_billing.plan_form, name="plan_edit"),
    path("premium/<int:pk>/ochirish/", views_billing.plan_delete, name="plan_delete"),
    path("premium/<int:pk>/holat/", views_billing.plan_toggle, name="plan_toggle"),
    path("obunalar/", views_billing.subscription_list, name="subscription_list"),
    path("obunalar/<int:pk>/bekor/", views_billing.subscription_cancel, name="subscription_cancel"),
    path("tolovlar/", views_billing.payment_list, name="payment_list"),
    path("promo-kodlar/", views_billing.promo_code_list, name="promo_code_list"),
    path("promo-kodlar/yangi/", views_billing.promo_code_form, name="promo_code_create"),
    path("promo-kodlar/<int:pk>/", views_billing.promo_code_form, name="promo_code_edit"),
    path("promo-kodlar/<int:pk>/ochirish/", views_billing.promo_code_delete, name="promo_code_delete"),
    path("promo-kodlar/<int:pk>/holat/", views_billing.promo_code_toggle, name="promo_code_toggle"),

    # Kontent
    path("bannerlar/", views_content.banner_list, name="banner_list"),
    path("bannerlar/yangi/", views_content.banner_form, name="banner_create"),
    path("bannerlar/<int:pk>/", views_content.banner_form, name="banner_edit"),
    path("bannerlar/<int:pk>/ochirish/", views_content.banner_delete, name="banner_delete"),
    path("bannerlar/<int:pk>/holat/", views_content.banner_toggle, name="banner_toggle"),

    path("bildirishnomalar/", views_content.notification_list, name="notification_list"),
    path("bildirishnomalar/yangi/", views_content.notification_form, name="notification_create"),
    path("bildirishnomalar/<int:pk>/", views_content.notification_form, name="notification_edit"),
    path("bildirishnomalar/<int:pk>/yuborish/", views_content.notification_send, name="notification_send"),
    path("bildirishnomalar/<int:pk>/ochirish/", views_content.notification_delete, name="notification_delete"),

    # Sozlamalar
    path("sozlamalar/", views_content.settings_view, name="settings"),
]
