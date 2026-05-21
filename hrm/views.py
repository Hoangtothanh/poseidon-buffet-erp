from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User, Group
import csv
from django.http import HttpResponse
from .models import NhanVien, CaLamViec, ChiTietCaLam, NgayNghi
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

    context = {
        'danh_sach_nv': danh_sach_nv,
        'tong_nhan_vien': tong_nhan_vien,
        'so_quan_ly': so_quan_ly,
        'so_phuc_vu': so_phuc_vu,
        'so_tai_khoan': so_tai_khoan,
        'roles': roles, 
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

    danh_sach_ca = CaLamViec.objects.filter(ngay_lam_viec=target_date).order_by('loai_ca', 'bo_phan')
    danh_sach_nv = NhanVien.objects.all().order_by('chuc_vu', 'ho_ten')
    
    nv_nghi_hom_nay = list(NgayNghi.objects.filter(ngay_nghi=target_date).values_list('nhan_vien_id', flat=True))

    tong_nv_hom_nay = ChiTietCaLam.objects.filter(ca_lam_viec__ngay_lam_viec=target_date).values('nhan_vien').distinct().count()
    ca_sang_count = ChiTietCaLam.objects.filter(ca_lam_viec__ngay_lam_viec=target_date, ca_lam_viec__loai_ca='morning').count()
    ca_toi_count = ChiTietCaLam.objects.filter(ca_lam_viec__ngay_lam_viec=target_date, ca_lam_viec__loai_ca='evening').count()

    context = {
        'target_date': target_date.strftime('%Y-%m-%d'),
        'danh_sach_ca': danh_sach_ca,
        'danh_sach_nv': danh_sach_nv,
        'nv_nghi_hom_nay': nv_nghi_hom_nay, 
        'tong_nv_hom_nay': tong_nv_hom_nay,
        'ca_sang_count': ca_sang_count,
        'ca_toi_count': ca_toi_count,
        'nv_nghi_off': len(nv_nghi_hom_nay),
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
                        ChiTietCaLam.objects.filter(ca_lam_viec=ca).delete()
                    else:
                        ca = CaLamViec.objects.create(ngay_lam_viec=ngay_lam, loai_ca=loai_ca, bo_phan=bo_phan, ghi_chu=ghi_chu)
                        
                    for nv_id in nhan_vien_ids:
                        ChiTietCaLam.objects.create(ca_lam_viec=ca, nhan_vien_id=nv_id)
                    messages.success(request, 'Đã lưu lịch trực thành công!')

            # LỆNH MỚI: BÁO NGHỈ PHÉP
            elif action == 'add_leave':
                nv_id = request.POST.get('nhan_vien_id')
                ngay_nghi = request.POST.get('ngay_nghi')
                ly_do = request.POST.get('ly_do_nghi')
                NgayNghi.objects.get_or_create(nhan_vien_id=nv_id, ngay_nghi=ngay_nghi, defaults={'ly_do': ly_do})
                messages.success(request, 'Đã ghi nhận đơn nghỉ phép thành công!')

        except Exception as e:
            messages.error(request, f'Lỗi hệ thống: {str(e)}')

        filter_date = request.POST.get('ngay_lam_viec') or request.POST.get('ngay_nghi') or timezone.now().strftime('%Y-%m-%d')
        return redirect(f'/shifts/?date={filter_date}')

    return redirect('shifts')


# --- HÀM MỚI: GIAO DIỆN LỊCH TUẦN ---
@login_required(login_url='login')
def weekly_shifts_view(request):
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday()) 
    dates = [start_of_week + timedelta(days=i) for i in range(7)]

    ca_trong_tuan = CaLamViec.objects.filter(ngay_lam_viec__in=dates).prefetch_related('chi_tiet_ca__nhan_vien')

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