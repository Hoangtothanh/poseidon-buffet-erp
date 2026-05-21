# File: accounts/urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.login_view, name='login'), 
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # ==========================================
    # CHUỖI 4 URL QUÊN MẬT KHẨU (Dùng auth_views. chứ KHÔNG PHẢI views.)
    # ==========================================
    # Bước 1: Điền Email
    path(
        'reset_password/', 
        auth_views.PasswordResetView.as_view(template_name="auth/password_reset_form.html"), 
        name="reset_password"
    ),
    
    # Bước 2: Thông báo "Đã gửi Email thành công, vui lòng check hộp thư"
    path(
        'reset_password_sent/', 
        auth_views.PasswordResetDoneView.as_view(template_name="auth/password_reset_done.html"), 
        name="password_reset_done"
    ),
    
    # Bước 3: Link từ Email bấm vào (Chứa mã token UID và Token)
    path(
        'reset/<uidb64>/<token>/', 
        auth_views.PasswordResetConfirmView.as_view(template_name="auth/password_reset_confirm.html"), 
        name="password_reset_confirm"
    ),
    
    # Bước 4: Thông báo đổi Pass thành công
    path(
        'reset_password_complete/', 
        auth_views.PasswordResetCompleteView.as_view(template_name="auth/password_reset_complete.html"), 
        name="password_reset_complete"
    ),
    
    path('reset_password/', auth_views.PasswordResetView.as_view(
    template_name="auth/password_reset_master.html",
    extra_context={'step': 'request'} ),  name="reset_password"),
]