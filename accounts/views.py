from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
import json
import random
from django.core.mail import send_mail
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.conf import settings

# ==========================================
# API KHÔI PHỤC MẬT KHẨU BẰNG OTP
# ==========================================

def api_send_otp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            
            user = User.objects.filter(email=email).first()
            if not user:
                return JsonResponse({'status': 'error', 'message': 'Email không tồn tại trong hệ thống!'}, status=400)
                
            # Tạo mã OTP ngẫu nhiên 6 số
            otp_code = str(random.randint(100000, 999999))
            
            # Lưu OTP vào cache, hết hạn sau 5 phút (300 giây)
            cache.set(f"otp_{email}", otp_code, timeout=300)
            
            # Gửi Email
            subject = "Mã xác thực OTP - Đặt lại mật khẩu Poseidon"
            message = f"Xin chào {user.first_name or user.username},\n\nMã OTP khôi phục mật khẩu của bạn là: {otp_code}\n\nMã này có hiệu lực trong vòng 5 phút. Vui lòng không chia sẻ mã này cho bất kỳ ai.\n\nPoseidon ERP."
            
            send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)
            
            # Ghi log (Tùy chọn)
            from core.models import SystemLog
            SystemLog.objects.create(
                user=user, action=f"Yêu cầu gửi mã OTP khôi phục mật khẩu",
                module="Bảo mật", level="warning"
            )
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Đã gửi mã OTP thành công.',
                'username': user.username
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

def api_verify_otp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            otp_input = data.get('otp', '').strip()
            
            cached_otp = cache.get(f"otp_{email}")
            
            if not cached_otp:
                return JsonResponse({'status': 'error', 'message': 'Mã OTP đã hết hạn hoặc chưa được gửi!'}, status=400)
                
            if str(cached_otp) != str(otp_input):
                return JsonResponse({'status': 'error', 'message': 'Mã OTP không chính xác!'}, status=400)
                
            # OTP đúng, đánh dấu email này đã xác thực (cho phép đổi pass)
            cache.set(f"otp_verified_{email}", True, timeout=300)
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

def api_reset_password(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            new_password = data.get('new_password', '')
            
            # Kiểm tra xem email này đã qua bước xác thực OTP chưa
            is_verified = cache.get(f"otp_verified_{email}")
            if not is_verified:
                return JsonResponse({'status': 'error', 'message': 'Lỗi bảo mật: Bạn chưa xác thực mã OTP!'}, status=403)
                
            if len(new_password) < 6:
                return JsonResponse({'status': 'error', 'message': 'Mật khẩu quá yếu (cần ít nhất 6 ký tự)!'}, status=400)
                
            user = User.objects.filter(email=email).first()
            if user:
                user.set_password(new_password)
                user.save()
                
                # Xóa cache
                cache.delete(f"otp_{email}")
                cache.delete(f"otp_verified_{email}")
                
                return JsonResponse({'status': 'success', 'message': 'Đổi mật khẩu thành công!'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Tài khoản không tồn tại!'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

# Đảm bảo import đúng model
# UserProfile đã được xóa, dùng NhanVien thay thế
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
                has_other_modules = (
                    quyen.table_view or 
                    quyen.booking_view or 
                    quyen.menu_view or 
                    quyen.inventory_view or 
                    quyen.report_view or 
                    quyen.system_all
                )
                if quyen.pos_view and not has_other_modules:
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
                has_other_modules = (
                    quyen.table_view or 
                    quyen.booking_view or 
                    quyen.menu_view or 
                    quyen.inventory_view or 
                    quyen.report_view or 
                    quyen.system_all
                )
                # NẾU CHỈ CÓ ĐÚNG QUYỀN POS: Bay thẳng ra màn hình bán hàng
                if quyen.pos_view and not has_other_modules:
                    return redirect('pos') 
                else:
                    # NẾU CÓ NHIỀU QUYỀN (Sơ đồ bàn, Booking...): Cho phép vào Dashboard để chọn
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
            new_username = request.POST.get('username', '').strip()
            
            # Kiểm tra trùng lặp tên đăng nhập
            if new_username and new_username != user.username:
                if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                    messages.error(request, f'Tên đăng nhập "{new_username}" đã tồn tại. Vui lòng chọn tên khác!')
                    return redirect('profile')
                user.username = new_username

            # Cập nhật bảng User mặc định
            if ho_ten:
                parts = ho_ten.split(' ', 1)
                user.last_name = parts[0]
                user.first_name = parts[1] if len(parts) > 1 else ''
            user.email = email
            user.save()
            
            # ĐỒNG BỘ SANG BẢNG NHÂN VIÊN (HRM)
            if not nhan_vien:
                nhan_vien = NhanVien(
                    user=user, 
                    ma_nv=f"NV-{user.id:03d}"
                )
            
            # Tự động cập nhật chức vụ theo Nhóm quyền phân quyền
            group = user.groups.first()
            if user.is_superuser:
                nhan_vien.chuc_vu = "Quản trị viên"
            elif group:
                nhan_vien.chuc_vu = group.name
            else:
                nhan_vien.chuc_vu = "Chưa phân bộ phận"
            
            nhan_vien.ho_ten = ho_ten or user.username
            nhan_vien.email = email
            nhan_vien.so_dien_thoai = so_dien_thoai
            if 'anh_dai_dien' in request.FILES:
                nhan_vien.anh_dai_dien = request.FILES['anh_dai_dien']
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