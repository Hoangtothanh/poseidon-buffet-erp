import io
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.core.management import call_command
from django.http import HttpResponse, HttpResponseForbidden

# Đảm bảo import đúng cấu trúc model mới
from .models import SystemSetting, SystemLog, QuyenTruyCap

# --- HELPER KIỂM TRA QUYỀN ---
def is_admin(user):
    # 1. Nếu là tài khoản gốc của Django (Superuser) -> Tự động cho qua
    if user.is_superuser:
        return True
    
    # 2. Nếu là nhân viên, kiểm tra xem chức vụ của họ có được gạt công tắc "system_all" không
    try:
        # Lấy chức vụ (Group) đầu tiên của nhân viên
        nhom_quyen = user.groups.first()
        if nhom_quyen and nhom_quyen.quyen.system_all:
            return True
    except Exception:
        pass
        
    return False

# ======================================================================
# 1. TRANG HIỂN THỊ CHÍNH (GET ONLY)
# ======================================================================
@login_required(login_url='login')
def settings_view(request):
    if not is_admin(request.user):
        messages.error(request, "Lỗi bảo mật: Bạn không có quyền truy cập trang Cài đặt Hệ thống!")
        return redirect('dashboard')

    setting, _ = SystemSetting.objects.get_or_create(id=1)

    # --- LẤY DỮ LIỆU ĐỂ HIỂN THỊ ---
    logs = SystemLog.objects.all().order_by('-timestamp')[:100]
    
    # Đảm bảo mọi Vai trò (Role) đều có bảng Quyền đi kèm
    roles = Group.objects.all()
    for r in roles:
        QuyenTruyCap.objects.get_or_create(group=r)

    context = {
        'setting': setting,
        'logs': logs,
        'roles': roles,
    }
    return render(request, 'system/settings.html', context)


# ======================================================================
# CÁC ENDPOINT RESTFUL XỬ LÝ DỮ LIỆU (CHỈ NHẬN POST)
# ======================================================================

# --- TAB 1: THÔNG TIN CHUNG (COMPANY PROFILE) ---
@login_required(login_url='login')
@require_POST
def settings_general(request):
    if not is_admin(request.user): return HttpResponseForbidden()
    
    setting, _ = SystemSetting.objects.get_or_create(id=1)
    try:
        vat = float(request.POST.get('vat_tax') or 0)
        sc = float(request.POST.get('service_charge') or 0)
        hold_time = int(request.POST.get('hold_table_time') or 15)
        deposit = int(request.POST.get('deposit_percent') or 20)
        
        if vat < 0 or vat > 100 or sc < 0 or sc > 100 or deposit < 0 or deposit > 100:
            messages.error(request, "Lỗi: Phần trăm % phải nằm trong khoảng từ 0 - 100!")
            return redirect('settings')
            
        setting.restaurant_name = request.POST.get('restaurant_name')
        setting.hotline = request.POST.get('hotline')
        setting.address = request.POST.get('address')
        setting.vat_tax = vat
        setting.service_charge = sc
        setting.hold_table_time = hold_time
        setting.deposit_percent = deposit
        setting.open_time = request.POST.get('open_time')
        setting.close_time = request.POST.get('close_time')
        
        if 'logo' in request.FILES:
            setting.logo = request.FILES['logo']
            
        setting.save()
        SystemLog.objects.create(user=request.user, action="Cập nhật Hồ sơ Doanh nghiệp", module="Cài đặt", level="info")
        messages.success(request, "Đã lưu Thông tin Doanh nghiệp thành công!")
    except ValueError:
        messages.error(request, "Dữ liệu cấu hình không hợp lệ!")
        
    return redirect('settings')


# --- TAB 2: TÍCH HỢP & THANH TOÁN (INTEGRATIONS) ---
@login_required(login_url='login')
@require_POST
def settings_integrations(request):
    if not is_admin(request.user): return HttpResponseForbidden()
    
    setting, _ = SystemSetting.objects.get_or_create(id=1)
    setting.bank_id = request.POST.get('bank_id')
    setting.bank_account_no = request.POST.get('bank_account_no')
    setting.bank_account_name = request.POST.get('bank_account_name')
    setting.save()
    
    SystemLog.objects.create(user=request.user, action="Cập nhật cấu hình API & Thanh toán", module="Cài đặt", level="info")
    messages.success(request, "Đã lưu cấu hình Tích hợp API & Thanh toán!")
    return redirect('/settings/#v-integrations')


# --- TẠO VAI TRÒ MỚI ---
@login_required(login_url='login')
@require_POST
def settings_create_role(request):
    if not is_admin(request.user): return HttpResponseForbidden()
    
    role_name = request.POST.get('role_name', '').strip()
    if role_name:
        new_group, created = Group.objects.get_or_create(name=role_name)
        if created:
            QuyenTruyCap.objects.create(group=new_group) # Tạo bảng phân quyền trống đi kèm
            SystemLog.objects.create(user=request.user, action=f"Tạo vai trò: {role_name}", module="Phân quyền", level="info")
            messages.success(request, f"Đã khởi tạo vai trò mới: {role_name}!")
        else:
            messages.error(request, "Lỗi: Tên vai trò này đã tồn tại trong hệ thống!")
    return redirect('/settings/#v-roles')


# --- XÓA VAI TRÒ ---
@login_required(login_url='login')
@require_POST
def settings_delete_role(request):
    if not is_admin(request.user): return HttpResponseForbidden()
    
    role_id = request.POST.get('role_id')
    try:
        group = Group.objects.get(id=role_id)
        group_name = group.name
        group.delete() # Xóa Role sẽ tự động Cascade xóa luôn bảng QuyenTruyCap liên kết
        SystemLog.objects.create(user=request.user, action=f"Xóa vai trò: {group_name}", module="Phân quyền", level="danger")
        messages.success(request, f"Đã thu hồi và xóa vai trò '{group_name}' thành công!")
    except Group.DoesNotExist:
        messages.error(request, "Lỗi: Vai trò không tồn tại!")
    return redirect('/settings/#v-roles')


# --- LƯU MA TRẬN PHÂN QUYỀN (CHUẨN CRUD) ---
@login_required(login_url='login')
@require_POST
def settings_permissions(request):
    if not is_admin(request.user): return HttpResponseForbidden()
    
    roles = Group.objects.all()
    for role in roles:
        quyen, _ = QuyenTruyCap.objects.get_or_create(group=role)
        
        # 1. Quyền Sơ đồ Bàn
        quyen.table_view = request.POST.get(f'perm[{role.id}][table][view]') == 'on'
        quyen.table_edit = request.POST.get(f'perm[{role.id}][table][edit]') == 'on'
        
        # 2. Quyền Đặt Bàn (Booking)
        quyen.booking_view = request.POST.get(f'perm[{role.id}][booking][view]') == 'on'
        quyen.booking_edit = request.POST.get(f'perm[{role.id}][booking][edit]') == 'on'
        quyen.booking_delete = request.POST.get(f'perm[{role.id}][booking][delete]') == 'on'
        
        # 3. Quyền Bán Hàng (POS)
        quyen.pos_view = request.POST.get(f'perm[{role.id}][pos][view]') == 'on'
        quyen.pos_edit = request.POST.get(f'perm[{role.id}][pos][edit]') == 'on'
        quyen.pos_checkout = request.POST.get(f'perm[{role.id}][pos][checkout]') == 'on'
        
        # 4. Quyền Thực đơn (Menu)
        quyen.menu_view = request.POST.get(f'perm[{role.id}][menu][view]') == 'on'
        quyen.menu_edit = request.POST.get(f'perm[{role.id}][menu][edit]') == 'on'
        quyen.menu_delete = request.POST.get(f'perm[{role.id}][menu][delete]') == 'on'
        
        # 5. Quyền Kho (Inventory)
        quyen.inventory_view = request.POST.get(f'perm[{role.id}][inventory][view]') == 'on'
        quyen.inventory_edit = request.POST.get(f'perm[{role.id}][inventory][edit]') == 'on'
        quyen.inventory_delete = request.POST.get(f'perm[{role.id}][inventory][delete]') == 'on'
        
        # 6. Quyền Báo cáo & Hệ thống
        quyen.report_view = request.POST.get(f'perm[{role.id}][report][view]') == 'on'
        quyen.system_all = request.POST.get(f'perm[{role.id}][system][all]') == 'on'
        
        quyen.save()
            
    SystemLog.objects.create(user=request.user, action="Cập nhật Ma trận Phân quyền CRUD", module="Phân quyền", level="warning")
    messages.success(request, "Đã thiết lập lại thành công Ma trận Phân quyền!")
    return redirect('/settings/#v-roles')

# --- CẤU HÌNH AI MACHINE LEARNING ---
@login_required(login_url='login')
@require_POST
def settings_ai(request):
    if not is_admin(request.user): return HttpResponseForbidden()
    
    setting, _ = SystemSetting.objects.get_or_create(id=1)
    setting.ai_dataset_window = request.POST.get('ai_dataset_window')
    setting.ai_prediction_window = request.POST.get('ai_prediction_window')
    setting.ai_weather_sync = request.POST.get('ai_weather_sync') == 'on'
    setting.save()
    
    SystemLog.objects.create(user=request.user, action="Thay đổi cấu hình Training AI", module="AI", level="warning")
    messages.success(request, "Đã lưu và đưa cấu hình AI mới vào tiến trình hàng đợi!")
    return redirect('/settings/#v-ai')


# --- SAO LƯU DỮ LIỆU (BACKUP) ---
@login_required(login_url='login')
@require_POST
def settings_backup(request):
    if not is_admin(request.user): return HttpResponseForbidden()
    
    out = io.StringIO()
    call_command('dumpdata', format='json', indent=2, stdout=out)
    response = HttpResponse(out.getvalue(), content_type='application/json')
    filename = f"Poseidon_DB_Backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    SystemLog.objects.create(user=request.user, action="Tải xuống bản sao lưu toàn bộ Database", module="Backup", level="danger")
    return response