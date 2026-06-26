from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User, Group
import csv
from django.http import HttpResponse
from .models import NhanVien, CaLamViec
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone

# Bổ sung ghi log hệ thống
try:
    from core.models import SystemLog
except ImportError:
    SystemLog = None


# ==========================================
# GIAO DIỆN DANH SÁCH & TÍNH KPI
# ==========================================
@login_required(login_url='login')
def employees_view(request):
    danh_sach_nv = NhanVien.objects.all().order_by('ma_nv')
    
    # Tính toán KPI
    tong_nhan_vien = danh_sach_nv.count()
    so_quan_ly = danh_sach_nv.filter(chuc_vu__icontains='Quản lý').count()
    so_phuc_vu = danh_sach_nv.filter(chuc_vu__icontains='Phục vụ').count()
    so_tai_khoan = danh_sach_nv.filter(user__isnull=False).count()

    # LẤY DANH SÁCH VAI TRÒ TỪ SETTINGS
    roles = Group.objects.all()

    # Logic gợi ý AI đơn giản
    today = timezone.now()
    weekday = today.weekday() # 0 = Monday, 6 = Sunday
    
    if weekday in [4, 5, 6]: # Thứ 6, 7, CN
        ai_suggestion = "Cuối tuần dự kiến rất đông khách, hệ thống AI đề xuất bố trí thêm 2-3 nhân viên phục vụ và 1 nhân viên bếp ca tối."
    elif weekday == 0:
        ai_suggestion = "Đầu tuần (Thứ 2) lượng khách thường vắng, có thể tối ưu giảm 1 nhân sự phục vụ ca sáng để tiết kiệm chi phí."
    else:
        ai_suggestion = "Lượng khách dự kiến ở mức ổn định trung bình, duy trì số lượng nhân viên trực như lịch tiêu chuẩn."

    context = {
        'danh_sach_nv': danh_sach_nv,
        'tong_nhan_vien': tong_nhan_vien,
        'so_quan_ly': so_quan_ly,
        'so_phuc_vu': so_phuc_vu,
        'so_tai_khoan': so_tai_khoan,
        'roles': roles, 
        'ai_suggestion': ai_suggestion,
    }
    return render(request, 'employees/employees.html', context)


# ==============================================================
# THÊM MỚI & CẬP NHẬT HỒ SƠ (CHUẨN LOGIC ĐỒNG BỘ ERP)
# ==============================================================
@login_required(login_url='login')
def save_employee(request):
    if request.method == 'POST':
        # Lấy dữ liệu thông tin cá nhân
        emp_id = request.POST.get('emp_id')
        ho_ten = request.POST.get('ho_ten', '').strip()
        gioi_tinh = request.POST.get('gioi_tinh')
        ngay_sinh = request.POST.get('ngay_sinh') or None
        so_dien_thoai = request.POST.get('so_dien_thoai')
        email = request.POST.get('email', '').strip()
        dia_chi = request.POST.get('dia_chi')
        chuc_vu = request.POST.get('chuc_vu') 
        
        # Lấy dữ liệu tài khoản
        tao_tai_khoan = request.POST.get('tao_tai_khoan') == 'on'
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        try:
            # DÙNG TRANSACTION BẢO VỆ DỮ LIỆU KÉP
            with transaction.atomic():
                user_obj = None
                
                # BƯỚC 1: XỬ LÝ TÀI KHOẢN (USER) TRƯỚC
                if tao_tai_khoan and username:
                    if emp_id: # Đang Sửa nhân viên cũ
                        nv_hien_tai = NhanVien.objects.get(id=emp_id)
                        if nv_hien_tai.user: # Đã có tài khoản 
                            user_obj = nv_hien_tai.user
                            
                            # Cập nhật username nếu có thay đổi
                            if username != user_obj.username:
                                if User.objects.filter(username=username).exclude(id=user_obj.id).exists():
                                    messages.error(request, f"Tên đăng nhập '{username}' đã tồn tại!")
                                    return redirect('employees')
                                user_obj.username = username

                            if password:
                                user_obj.set_password(password)
                            
                            # 🚨 FIX QUAN TRỌNG: Phải update Email vào bảng User để Quên mật khẩu hoạt động
                            user_obj.email = email 
                            user_obj.save()
                        else: # Mới cấp tài khoản cho NV cũ
                            if User.objects.filter(username=username).exists():
                                messages.error(request, f"Tên đăng nhập '{username}' đã tồn tại!")
                                return redirect('employees')
                            user_obj = User.objects.create_user(username=username, email=email, password=password)
                    
                    else: # Thêm Mới Nhân viên hoàn toàn
                        if User.objects.filter(username=username).exists():
                            messages.error(request, f"Tên đăng nhập '{username}' đã tồn tại!")
                            return redirect('employees')
                        user_obj = User.objects.create_user(username=username, email=email, password=password)
                    
                    # Đẩy họ tên vào User (phục vụ hiển thị trên Menu Dropdown Avatar)
                    if user_obj:
                        parts = ho_ten.split(' ', 1)
                        user_obj.last_name = parts[0]
                        user_obj.first_name = parts[1] if len(parts) > 1 else ''
                        user_obj.save()
                        
                        # BƯỚC 1.5: GÁN VAI TRÒ DỰA THEO CHỨC VỤ
                        user_obj.groups.clear() # Xóa sạch quyền cũ (nếu đổi chức vụ)
                        if chuc_vu:
                            group = Group.objects.filter(name__iexact=chuc_vu).first()
                            if group:
                                user_obj.groups.add(group)

                # BƯỚC 2: LƯU HỒ SƠ NHÂN VIÊN
                if emp_id: # Cập nhật
                    nv = NhanVien.objects.get(id=emp_id)
                    nv.ho_ten = ho_ten
                    nv.gioi_tinh = gioi_tinh
                    nv.ngay_sinh = ngay_sinh
                    nv.so_dien_thoai = so_dien_thoai
                    nv.email = email
                    nv.dia_chi = dia_chi
                    nv.chuc_vu = chuc_vu
                    if user_obj:
                        nv.user = user_obj 
                    nv.save()
                    messages.success(request, f"Đã cập nhật hồ sơ nhân viên {ho_ten}!")
                
                else: # Thêm Mới
                    # Tự động sinh Mã Nhân Viên (NV-001, NV-002...)
                    last_nv = NhanVien.objects.order_by('id').last()
                    if last_nv and '-' in last_nv.ma_nv:
                        try:
                            new_id = int(last_nv.ma_nv.split('-')[1]) + 1
                            ma_nv = f"NV-{new_id:03d}"
                        except ValueError:
                            ma_nv = f"NV-{last_nv.id + 1:03d}"
                    else:
                        ma_nv = "NV-001"
                    
                    NhanVien.objects.create(
                        ma_nv=ma_nv, ho_ten=ho_ten, gioi_tinh=gioi_tinh,
                        ngay_sinh=ngay_sinh, so_dien_thoai=so_dien_thoai,
                        email=email, dia_chi=dia_chi, chuc_vu=chuc_vu,
                        user=user_obj 
                    )
                    messages.success(request, f"Đã thêm nhân viên mới: {ho_ten} (Mã: {ma_nv})!")
                    
                # BƯỚC 3: LƯU LOG 
                if SystemLog:
                    action_text = "Cập nhật hồ sơ" if emp_id else "Thêm nhân viên mới"
                    SystemLog.objects.create(
                        user=request.user, action=f"{action_text}: {ho_ten}",
                        module="Nhân sự", level="info"
                    )

        except Exception as e:
            messages.error(request, f"Lỗi hệ thống: {str(e)}")
            
    return redirect('employees')


# ==========================================
# XÓA HỒ SƠ KÈM XÓA TÀI KHOẢN AN TOÀN
# ==========================================
@login_required(login_url='login')
def delete_employee(request, emp_id):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                nv = get_object_or_404(NhanVien, id=emp_id)
                ten_nv = nv.ho_ten
                user_obj = nv.user
                
                # Xóa nhân viên
                nv.delete()
                
                # Xóa luôn tài khoản đăng nhập (Tránh để lại tài khoản mồ côi)
                # Bỏ qua không xóa nếu tài khoản đó là SuperAdmin để bảo vệ hệ thống
                if user_obj and not user_obj.is_superuser: 
                    user_obj.delete()
                
                if SystemLog:
                    SystemLog.objects.create(
                        user=request.user, action=f"Xóa hồ sơ nhân viên: {ten_nv}",
                        module="Nhân sự", level="warning"
                    )
                    
                messages.success(request, f'Đã xóa nhân viên {ten_nv} và thu hồi tài khoản thành công!')
        except Exception as e:
            messages.error(request, f'Không thể xóa: {str(e)}')
            
    return redirect('employees')


# ==========================================
# XUẤT EXCEL
# ==========================================
@login_required(login_url='login')
def export_employees_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Danh_Sach_Nhan_Vien_Poseidon.csv"'
    response.write('\ufeff'.encode('utf8')) # Hỗ trợ tiếng Việt
    writer = csv.writer(response)
    
    writer.writerow(['Mã NV', 'Họ Tên', 'Giới Tính', 'Ngày Sinh', 'SĐT', 'Email', 'Chức Vụ', 'Tài Khoản ERP'])
    
    for nv in NhanVien.objects.all().order_by('ma_nv'):
        erp_acc = nv.user.username if nv.user else "Không có"
        ngay_sinh = nv.ngay_sinh.strftime("%d/%m/%Y") if nv.ngay_sinh else ""
        writer.writerow([
            nv.ma_nv, nv.ho_ten, nv.gioi_tinh, ngay_sinh, 
            nv.so_dien_thoai, nv.email, nv.chuc_vu, erp_acc
        ])
        
    return response


# ==========================================
# CA LÀM VIỆC
# ==========================================
@login_required(login_url='login')
def shifts_view(request):
    filter_date_str = request.GET.get('date')
    if filter_date_str:
        try:
            target_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = timezone.now().date()
    else:
        target_date = timezone.now().date()

    danh_sach_ca = CaLamViec.objects.filter(ngay_lam_viec=target_date).exclude(loai_ca='nghi_phep').order_by('loai_ca', 'bo_phan')
    
    from datetime import timedelta
    import json
    
    start_date = target_date - timedelta(days=15)
    end_date = target_date + timedelta(days=15)
    ca_nghi_all = CaLamViec.objects.filter(ngay_lam_viec__range=[start_date, end_date], loai_ca='nghi_phep').prefetch_related('nhan_vien')
    
    leave_dict_target = {}
    leave_json = {}
    for ca in ca_nghi_all:
        date_str = ca.ngay_lam_viec.strftime('%Y-%m-%d')
        if date_str not in leave_json:
            leave_json[date_str] = {}
        for nv in ca.nhan_vien.all():
            leave_json[date_str][nv.id] = ca.ghi_chu or 'Nghỉ phép'
            if ca.ngay_lam_viec == target_date:
                leave_dict_target[nv.id] = ca.ghi_chu or 'Nghỉ phép'
            
    danh_sach_nv = NhanVien.objects.all().order_by('chuc_vu', 'ho_ten')

    tong_nv_hom_nay = CaLamViec.objects.filter(ngay_lam_viec=target_date).exclude(loai_ca='nghi_phep').values('nhan_vien').distinct().count()
    ca_sang_count = CaLamViec.objects.filter(ngay_lam_viec=target_date, loai_ca='morning').values('nhan_vien').count()
    ca_toi_count = CaLamViec.objects.filter(ngay_lam_viec=target_date, loai_ca='evening').values('nhan_vien').count()
    
    nv_nghi_hom_nay = list(leave_dict_target.keys())
    
    # Logic gợi ý AI từ ai_analytics
    ai_suggestion = "Lượng khách dự kiến ở mức ổn định trung bình, duy trì số lượng nhân viên trực như lịch tiêu chuẩn."
    try:
        from ai_analytics.views import get_ai_features
        now = timezone.now()
        features = get_ai_features(now.date(), target_date, now.hour)
        
        tong_khach = features.get('pax_forecast', 0)
        pax_trua = features.get('pax_trua', 0)
        pax_toi = features.get('pax_toi', 0)
        staff_trua = features.get('staff_required_trua', 0)
        staff_toi = features.get('staff_required_toi', 0)
        
        weather = features.get('weather_data')
        weather_str = ""
        if weather:
            weather_str = f"Thời tiết: {weather.get('icon', '')} {weather.get('temp_max', '')}°C ({weather.get('description', '')}). "
            
        # Lấy nhân viên phục vụ thực tế đã xếp
        ca_lam_target = CaLamViec.objects.filter(ngay_lam_viec=target_date, bo_phan='service')
        actual_service_trua = 0
        actual_service_toi = 0
        for ca in ca_lam_target:
            if ca.loai_ca in ['morning', 'full']:
                actual_service_trua += ca.nhan_vien.count()
            if ca.loai_ca in ['evening', 'full']:
                actual_service_toi += ca.nhan_vien.count()
                
        # Tính toán thừa/thiếu ca trưa
        if actual_service_trua < staff_trua:
            status_trua = f"<span class='d-block mt-1 ms-3 text-danger fw-bold'>👉 Thiếu {staff_trua - actual_service_trua} Nhân viên phục vụ</span>"
        elif actual_service_trua > staff_trua:
            status_trua = f"<span class='d-block mt-1 ms-3 text-warning fw-bold'>👉 Thừa {actual_service_trua - staff_trua} Nhân viên phục vụ</span>"
        else:
            status_trua = f"<span class='d-block mt-1 ms-3 text-success fw-bold'>👉 Đủ Nhân viên phục vụ</span>"

        # Tính toán thừa/thiếu ca tối
        if actual_service_toi < staff_toi:
            status_toi = f"<span class='d-block mt-1 ms-3 text-danger fw-bold'>👉 Thiếu {staff_toi - actual_service_toi} Nhân viên phục vụ</span>"
        elif actual_service_toi > staff_toi:
            status_toi = f"<span class='d-block mt-1 ms-3 text-warning fw-bold'>👉 Thừa {actual_service_toi - staff_toi} Nhân viên phục vụ</span>"
        else:
            status_toi = f"<span class='d-block mt-1 ms-3 text-success fw-bold'>👉 Đủ Nhân viên phục vụ</span>"
            
        ai_suggestion = (
            f"Dự báo <b>{tong_khach} khách</b>. "
            f"{weather_str}"
            f"<ul style='margin-bottom: 0; padding-left: 20px; margin-top: 5px;'>"
            f"<li><b>Ca Trưa</b>: ~{pax_trua} khách (Khuyến nghị: {staff_trua} Nhân viên phục vụ | Đã xếp: {actual_service_trua} Nhân viên phục vụ) {status_trua}</li>"
            f"<li><b>Ca Tối</b>: ~{pax_toi} khách (Khuyến nghị: {staff_toi} Nhân viên phục vụ | Đã xếp: {actual_service_toi} Nhân viên phục vụ) {status_toi}</li>"
            f"</ul>"
        )
    except Exception as e:
        print("Lỗi tính ai_suggestion shifts:", e)
    
    context = {
        'target_date': target_date.strftime('%Y-%m-%d'),
        'danh_sach_ca': danh_sach_ca,
        'danh_sach_nv': danh_sach_nv,
        'ai_suggestion': ai_suggestion,
        'nv_nghi_hom_nay': nv_nghi_hom_nay, 
        'tong_nv_hom_nay': tong_nv_hom_nay,
        'ca_sang_count': ca_sang_count,
        'ca_toi_count': ca_toi_count,
        'nv_nghi_off': len(nv_nghi_hom_nay),
        'leave_json': json.dumps(leave_json, ensure_ascii=False)
    }
    return render(request, 'employees/shifts.html', context)


# --- HÀM QUẢN LÝ THÊM/SỬA/XÓA VÀ "BÁO NGHỈ" ---
@login_required(login_url='login')
def manage_shift(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            if action == 'delete':
                ca_id = request.POST.get('ca_id')
                CaLamViec.objects.get(id=ca_id).delete()
                messages.success(request, 'Đã hủy phân ca làm việc thành công!')

            elif action == 'save':
                ca_id = request.POST.get('ca_id')
                ngay_lam = request.POST.get('ngay_lam_viec')
                loai_ca = request.POST.get('loai_ca')
                bo_phan = request.POST.get('bo_phan')
                ghi_chu = request.POST.get('ghi_chu')
                nhan_vien_ids = request.POST.getlist('nhan_vien_ids')
                
                with transaction.atomic():
                    if ca_id:
                        ca = CaLamViec.objects.get(id=ca_id)
                        ca.ngay_lam_viec = ngay_lam
                        ca.loai_ca = loai_ca
                        ca.bo_phan = bo_phan
                        ca.ghi_chu = ghi_chu
                        ca.save()
                        ca.nhan_vien.clear()
                    else:
                        ca = CaLamViec.objects.create(ngay_lam_viec=ngay_lam, loai_ca=loai_ca, bo_phan=bo_phan, ghi_chu=ghi_chu)
                        
                    for nv_id in nhan_vien_ids:
                        ca.nhan_vien.add(nv_id)
                    messages.success(request, 'Đã lưu lịch trực thành công!')

            # LỆNH MỚI: BÁO NGHỈ PHÉP
            elif action == 'add_leave':
                nv_id = request.POST.get('nhan_vien_id')
                ngay_nghi = request.POST.get('ngay_nghi')
                ly_do = request.POST.get('ly_do_nghi')
                ca_nghi, created = CaLamViec.objects.get_or_create(ngay_lam_viec=ngay_nghi, loai_ca='nghi_phep', bo_phan='other', defaults={'ghi_chu': ly_do})
                ca_nghi.nhan_vien.add(nv_id)
                messages.success(request, 'Đã ghi nhận đơn nghỉ phép thành công!')

        except Exception as e:
            messages.error(request, f'Lỗi hệ thống: {str(e)}')

        filter_date = request.POST.get('ngay_lam_viec') or request.POST.get('ngay_nghi') or timezone.now().strftime('%Y-%m-%d')
        from django.urls import reverse
        return redirect(f"{reverse('shifts')}?date={filter_date}")

    return redirect('shifts')


# --- HÀM MỚI: GIAO DIỆN LỊCH TUẦN ---
@login_required(login_url='login')
def weekly_shifts_view(request):
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday()) 
    dates = [start_of_week + timedelta(days=i) for i in range(7)]

    ca_trong_tuan = CaLamViec.objects.filter(ngay_lam_viec__in=dates).exclude(loai_ca='nghi_phep').prefetch_related('nhan_vien')

    week_data = {d: {'morning': [], 'evening': [], 'full': []} for d in dates}
    for ca in ca_trong_tuan:
        week_data[ca.ngay_lam_viec][ca.loai_ca].append(ca)

    context = {
        'dates': dates,
        'week_data': week_data,
        'start_of_week': start_of_week,
        'end_of_week': dates[-1]
    }
    return render(request, 'employees/weekly_shifts.html', context)

# --- HÀM MỚI: PHÂN CA NHANH ---
@login_required(login_url='login')
def quick_shift(request):
    if request.method == 'POST':
        shift_type = request.POST.get('shift_type')
        target_date_str = request.POST.get('target_date')
        
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            target_date = timezone.now().date()
            
        # Determine the shift name for messages
        shift_name = 'sáng' if shift_type == 'morning' else 'tối'
        
        try:
            with transaction.atomic():
                import random
                
                # 1. Lấy dữ liệu dự báo AI cho ngày và ca này
                required_service = 3 # Mặc định nếu không có AI
                
                try:
                    from ai_analytics.views import get_ai_features
                    now = timezone.now()
                    features = get_ai_features(now.date(), target_date, now.hour)
                    if shift_type == 'morning':
                        required_service = features.get('staff_required_trua', 3)
                    else:
                        required_service = features.get('staff_required_toi', 3)
                except Exception as e:
                    print(f"Error getting AI features in quick_shift: {e}")
                    pass

                already_scheduled_count = 0
                added_service_count = 0

                # Tự động phân bổ theo chức vụ
                for dept in ['service', 'kitchen', 'cashier']:
                    ca, _ = CaLamViec.objects.get_or_create(
                        ngay_lam_viec=target_date, 
                        loai_ca=shift_type, 
                        bo_phan=dept, 
                        defaults={'ghi_chu': f'Phân ca nhanh tự động (AI đề xuất {required_service} NV)' if dept == 'service' else 'Phân ca nhanh tự động'}
                    )
                    
                    if dept == 'service':
                        # Lấy danh sách ID nhân viên đã được xếp ca này trước đó
                        already_scheduled_ids = list(ca.nhan_vien.values_list('id', flat=True))
                        already_scheduled_count = len(already_scheduled_ids)
                        
                        # Tính số nhân viên phục vụ cần thêm để đạt mức khuyến nghị của AI
                        needed = max(0, required_service - already_scheduled_count)
                        
                        if needed > 0:
                            # Lấy tất cả phục vụ
                            all_service = list(NhanVien.objects.filter(chuc_vu__icontains='Phục vụ'))
                            
                            # Lấy danh sách ID nhân viên đã báo nghỉ vào target_date
                            nghi_ids = CaLamViec.objects.filter(ngay_lam_viec=target_date, loai_ca='nghi_phep').values_list('nhan_vien__id', flat=True)
                            
                            # Lọc ra những người không nghỉ và chưa được xếp ca này
                            available_service = [
                                nv for nv in all_service 
                                if nv.id not in nghi_ids and nv.id not in already_scheduled_ids
                            ]
                            
                            # Chọn ngẫu nhiên số lượng cần thêm
                            nvs = random.sample(available_service, min(len(available_service), needed))
                            added_service_count = len(nvs)
                        else:
                            nvs = []
                    elif dept == 'kitchen':
                        nvs = NhanVien.objects.filter(chuc_vu__icontains='Bếp')
                    elif dept == 'cashier':
                        nvs = NhanVien.objects.filter(chuc_vu__icontains='Thu ngân')
                        
                    for nv in nvs:
                        ca.nhan_vien.add(nv)
                
                # Các nhân viên khác
                ca_other, _ = CaLamViec.objects.get_or_create(
                     ngay_lam_viec=target_date, 
                     loai_ca=shift_type, 
                     bo_phan='other', 
                     defaults={'ghi_chu': 'Phân ca nhanh tự động (Khác)'}
                )
                nvs_other = NhanVien.objects.exclude(chuc_vu__icontains='Phục vụ').exclude(chuc_vu__icontains='Bếp').exclude(chuc_vu__icontains='Thu ngân')
                for nv in nvs_other:
                    ca_other.nhan_vien.add(nv)

                if SystemLog:
                    SystemLog.objects.create(
                        user=request.user, action=f"Sử dụng phân ca {shift_name} nhanh cho ngày {target_date.strftime('%d/%m/%Y')}",
                        module="Nhân sự", level="info"
                    )
                    
            if added_service_count > 0:
                success_msg = f'Đã phân ca {shift_name} nhanh cho ngày {target_date.strftime("%d/%m/%Y")}! AI đã bổ sung thêm {added_service_count} nhân viên phục vụ (trước đó đã xếp {already_scheduled_count} NV, đạt tổng {already_scheduled_count + added_service_count}/{required_service} NV theo khuyến nghị của AI).'
            else:
                success_msg = f'Ca {shift_name} ngày {target_date.strftime("%d/%m/%Y")} đã được xếp đủ {already_scheduled_count} nhân viên phục vụ (Khuyến nghị của AI: {required_service} NV). Không cần bổ sung thêm.'
                
            messages.success(request, success_msg)
        except Exception as e:
            messages.error(request, f'Lỗi phân ca nhanh: {str(e)}')
            
        from django.urls import reverse
        return redirect(f"{reverse('shifts')}?date={target_date.strftime('%Y-%m-%d')}")
        
    return redirect('employees')