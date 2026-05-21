from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache

# Đảm bảo import đúng model
from .models import UserProfile 
from core.models import SystemLog
from hrm.models import NhanVien

# ==========================================
# HÀM BỔ TRỢ: LẤY IP CLIENT ĐỂ LÀM BẢO MẬT
# ==========================================
def get_client_ip(request):
    """Trích xuất địa chỉ IP thực của Client (Xuyên qua Proxy/Cloudflare nếu có)"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# ==========================================
# 1. XỬ LÝ ĐĂNG NHẬP (ANTI BRUTE-FORCE & ĐIỀU HƯỚNG THÔNG MINH)
# ==========================================
def login_view(request):
    # Nếu người dùng đã đăng nhập rồi thì kiểm tra quyền để đá về đúng trang
    if request.user.is_authenticated:
        if not request.user.is_superuser:
            try:
                quyen = request.user.groups.first().quyen
                if quyen.pos_view and not quyen.inventory_view and not quyen.report_view and not quyen.system_all:
                    return redirect('pos')
            except Exception:
                pass
        return redirect('dashboard') 

    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        # 🚨 BẢO MẬT: KIỂM TRA BRUTE-FORCE BẰNG CACHE
        ip = get_client_ip(request)
        cache_key = f'login_attempts_{ip}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            # Ghi log cảnh báo bạo lực (Brute-force attack)
            SystemLog.objects.create(
                user=None, action=f"Phát hiện tấn công Brute-force từ IP: {ip}. Đã tự động khóa.",
                module="Bảo mật", level="danger"
            )
            messages.error(request, 'Tài khoản của bạn đã bị khóa tạm thời 5 phút do nhập sai quá nhiều lần. Vui lòng thử lại sau!')
            return render(request, 'auth/login.html')

        user = authenticate(request, username=u, password=p)
        
        if user is not None:
            # Reset biến đếm khi đăng nhập thành công
            cache.delete(cache_key)
            login(request, user)
            
            # Ghi Log hệ thống kèm IP Client
            SystemLog.objects.create(
                user=user, action=f"Đăng nhập thành công (IP: {ip})",
                module="Hệ thống", level="info"
            )
            
            # 🚨 LOGIC ĐIỀU HƯỚNG THÔNG MINH SAU KHI ĐĂNG NHẬP
            if user.is_superuser:
                return redirect('dashboard')
                
            # Lấy bảng quyền của nhân viên này
            try:
                quyen = user.groups.first().quyen
                # NẾU LÀ FRONT-OFFICE (PHỤC VỤ/THU NGÂN): Có quyền POS nhưng KHÔNG có quyền Kho/Báo cáo/Cài đặt
                if quyen.pos_view and not quyen.inventory_view and not quyen.report_view and not quyen.system_all:
                    return redirect('pos') # Bay thẳng ra màn hình bán hàng
                else:
                    # NẾU LÀ BACK-OFFICE (QUẢN LÝ, BẾP, KHO): Cho phép vào ERP
                    return redirect('dashboard')
            except Exception:
                # Trạng thái mặc định nếu user chưa được phân nhóm
                return redirect('dashboard')
        else:
            # Tăng biến đếm nhập sai lên 1 (Khóa trong 5 phút = 300 giây)
            cache.set(cache_key, attempts + 1, timeout=300)
            
            # Ghi log cảnh báo nhập sai
            SystemLog.objects.create(
                user=None, action=f"Đăng nhập thất bại. Tài khoản: {u} (IP: {ip}). Sai {attempts + 1}/5 lần.",
                module="Bảo mật", level="warning"
            )
            messages.error(request, f'Tài khoản hoặc mật khẩu không chính xác! (Nhập sai {attempts + 1}/5 lần)')
            
    return render(request, 'auth/login.html')

# ==========================================
# 2. XỬ LÝ ĐĂNG XUẤT
# ==========================================
def logout_view(request):
    if request.user.is_authenticated:
        ip = get_client_ip(request)
        # Ghi Log trước khi đăng xuất
        SystemLog.objects.create(
            user=request.user, action=f"Đăng xuất khỏi hệ thống (IP: {ip})",
            module="Hệ thống", level="info"
        )
    logout(request)
    messages.success(request, 'Đã đăng xuất thành công!')
    return redirect('login')

# ==========================================
# 3. TRANG HỒ SƠ & ĐỔI MẬT KHẨU (NÂNG CẤP ERP)
# ==========================================
@login_required(login_url='login')
def profile_view(request):
    user = request.user
    ip = get_client_ip(request)
    
    # KẾT NỐI VỚI MODULE NHÂN SỰ (HRM)
    nhan_vien = NhanVien.objects.filter(user=user).first()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # --- CẬP NHẬT THÔNG TIN ---
        if action == 'update_info':
            ho_ten = request.POST.get('ho_ten', '').strip()
            email = request.POST.get('email', '').strip()
            so_dien_thoai = request.POST.get('so_dien_thoai', '').strip()
            
            # Cập nhật bảng User mặc định
            if ho_ten:
                parts = ho_ten.split(' ', 1)
                user.last_name = parts[0]
                user.first_name = parts[1] if len(parts) > 1 else ''
            user.email = email
            user.save()
            
            # Cập nhật UserProfile (Avatar & SĐT)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.so_dien_thoai = so_dien_thoai
            if 'anh_dai_dien' in request.FILES:
                profile.anh_dai_dien = request.FILES['anh_dai_dien']
            profile.save()
            
            # ĐỒNG BỘ SANG BẢNG NHÂN VIÊN (HRM)
            if nhan_vien:
                nhan_vien.ho_ten = ho_ten
                nhan_vien.email = email
                nhan_vien.so_dien_thoai = so_dien_thoai
                nhan_vien.save()

            # GHI LOG HỆ THỐNG
            SystemLog.objects.create(
                user=user, action="Cập nhật thông tin Hồ sơ cá nhân",
                module="Hồ sơ", level="info"
            )
            
            messages.success(request, 'Cập nhật thông tin hồ sơ thành công!')
            return redirect('profile')
            
        # --- ĐỔI MẬT KHẨU ---
        elif action == 'change_password':
            old_password = request.POST.get('old_password')
            new_password = request.POST.get('new_password')
            
            if not user.check_password(old_password):
                messages.error(request, 'Mật khẩu hiện tại không chính xác!')
            elif len(new_password) < 6:
                messages.error(request, 'Hệ thống từ chối: Mật khẩu mới quá yếu (Cần ít nhất 6 ký tự)!')
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user) # Giữ phiên đăng nhập
                
                # GHI LOG CẢNH BÁO BẢO MẬT
                SystemLog.objects.create(
                    user=user, action=f"Đổi mật khẩu tài khoản thành công (IP: {ip})",
                    module="Bảo mật", level="warning"
                )
                messages.success(request, 'Đổi mật khẩu thành công! Tài khoản của bạn đã được bảo vệ.')
                
            return redirect('profile')

    # Truyền dữ liệu nhân viên ra ngoài template
    context = {'nhan_vien': nhan_vien}
    return render(request, 'auth/profile.html', context)