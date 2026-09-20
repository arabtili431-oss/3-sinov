from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("config/", views.app_config, name="config"),
    path("banners/", views.BannerListView.as_view(), name="banners"),

    # Kurslar
    path("categories/", views.CategoryListView.as_view(), name="categories"),
    path("courses/", views.CourseListView.as_view(), name="courses"),
    path("courses/<slug:slug>/", views.CourseDetailView.as_view(), name="course-detail"),
    path("courses/<slug:slug>/enroll/", views.enroll, name="course-enroll"),
    path("my/courses/", views.my_courses, name="my-courses"),

    # Darslar
    path("lessons/<int:pk>/", views.LessonDetailView.as_view(), name="lesson-detail"),
    path("lessons/<int:pk>/video/", views.LessonVideoView.as_view(), name="lesson-video"),
    path("lessons/<int:pk>/complete/", views.lesson_complete, name="lesson-complete"),
    path("lessons/<int:pk>/quiz/", views.lesson_quiz, name="lesson-quiz"),
    path("lessons/<int:pk>/quiz/submit/", views.lesson_quiz_submit, name="lesson-quiz-submit"),

    # Reyting
    path("leaderboard/", views.leaderboard, name="leaderboard"),

    # Premium
    path("plans/", views.PlanListView.as_view(), name="plans"),
    path("my/subscription/", views.my_subscription, name="my-subscription"),
    path("subscribe/", views.subscribe, name="subscribe"),

    # Do'kon
    path("shop/categories/", views.ProductCategoryListView.as_view(), name="shop-categories"),
    path("shop/products/", views.ProductListView.as_view(), name="products"),
    path("shop/products/<slug:slug>/", views.ProductDetailView.as_view(), name="product-detail"),
    path("shop/products/<slug:slug>/reviews/", views.product_reviews, name="product-reviews"),
    path("shop/products/<slug:slug>/redeem/", views.product_redeem, name="product-redeem"),
    path("shop/cart/", views.cart_view, name="cart-view"),
    path("shop/cart/add/", views.cart_add, name="cart-add"),
    path("shop/cart/remove/", views.cart_remove, name="cart-remove"),
    path("shop/cart/checkout/", views.cart_checkout, name="cart-checkout"),
    path("shop/orders/", views.create_order, name="order-create"),
    path("my/orders/", views.my_orders, name="my-orders"),

    # Bildirishnomalar
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/<int:pk>/read/", views.notification_read, name="notification-read"),
]
