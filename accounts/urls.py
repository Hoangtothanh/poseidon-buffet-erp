# File: accounts/urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Trang đăng nhập chính (chỉ để 1 URL, bỏ path rỗng '' gây trùng lặp)
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('profile/', views.profile_view, name='profile'),

    # ==========================================
    # CHUỖI 3 API QUÊN MẬT KHẨU BẰNG OTP
    # ==========================================
    path('api/forgot-password/send-otp/', views.api_send_otp, name='api_send_otp'),
    path('api/forgot-password/verify-otp/', views.api_verify_otp, name='api_verify_otp'),
    path('api/forgot-password/reset/', views.api_reset_password, name='api_reset_password'),
]