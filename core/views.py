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

# --- TẠO DỮ LIỆU MẪU HÔM NAY ---
@login_required(login_url='login')
@require_POST
def settings_seed_data_today(request):
    if not is_admin(request.user): return HttpResponseForbidden()
    
    from pos.models import HoaDon, ChiTietHoaDon
    from reception.models import BanAn
    from menu.models import ThucDon
    from customers.models import KhachHang
    from inventory.models import NguyenLieu, PhieuKho, ChiTietPhieuKho, NhaCungCap
    import random
    import datetime as dt
    from datetime import timedelta
    
    ban_list    = list(BanAn.objects.exclude(trang_thai='da_xoa'))
    buffet_list = list(ThucDon.objects.filter(loai_mon='goi_buffet', trang_thai=True))
    drink_list  = list(ThucDon.objects.filter(loai_mon='do_uong', trang_thai=True))
    kh_list     = list(KhachHang.objects.filter(is_active=True))
    nl_list     = list(NguyenLieu.objects.all())
    ncc_list    = list(NhaCungCap.objects.all())
    
    # ─────────────────────────────────────────────────────────────
    # LẤY CÁC NGÀY TỪ FORM
    # ─────────────────────────────────────────────────────────────
    seed_dates_str = request.POST.get('seed_dates')
    target_dates = []
    if seed_dates_str:
        for d_str in seed_dates_str.split(','):
            if d_str.strip():
                target_dates.append(dt.datetime.strptime(d_str.strip(), '%Y-%m-%d').date())
    else:
        target_dates = [timezone.now().date()]
        
    if not ban_list or not buffet_list:
        messages.error(request, "Vui lòng tạo bàn và ít nhất 1 Gói Buffet trước khi sinh dữ liệu!")
        return redirect('/settings/#v-backup')

    if request.POST.get('reset_inventory') == 'on':
        import random
        for nl in nl_list:
            nl.ton_kho = random.randint(10, 50)
            nl.save()
        messages.info(request, "Đã dọn dẹp rác tồn kho, tất cả nguyên liệu đã được đưa về mức 10-50.")

    total_hd = 0
    for d in target_dates:
        total_hd += _generate_seed_for_single_date(request, d, ban_list, buffet_list, drink_list, kh_list, nl_list, ncc_list)

    from core.models import SystemLog
    SystemLog.objects.create(
        user=request.user,
        action=f"Khởi tạo {total_hd} hóa đơn mẫu cho {len(target_dates)} ngày",
        module="Hệ thống", level="warning"
    )
    messages.success(request, f"✅ Đã tạo {total_hd} hóa đơn mẫu cho {len(target_dates)} ngày!")
    return redirect('/settings/#v-backup')

def _generate_seed_for_single_date(request, today, ban_list, buffet_list, drink_list, kh_list, nl_list, ncc_list):
    from pos.models import HoaDon, ChiTietHoaDon
    from inventory.models import PhieuKho, ChiTietPhieuKho
    import random
    import datetime as dt
    from datetime import timedelta
    from django.utils import timezone
    
    # Chuẩn bị danh sách đồ uống ưu tiên (Pepsi, Aqua)
    drink_priority = [d for d in drink_list if 'pepsi' in d.ten_mon.lower() or 'aqua' in d.ten_mon.lower()]
    
    # Tạo sẵn 1 Phiếu xuất kho tự động cho đồ uống của ngày hôm nay
    phieu_xuat_do_uong = None
    if nl_list:
        phieu_xuat_do_uong = PhieuKho.objects.create(
            loai_phieu='xuat',
            nguoi_thuc_hien=request.user,
            ngay_thuc_hien=timezone.make_aware(dt.datetime.combine(today, dt.time(22, 30))),
            da_thanh_toan=True,
            ghi_chu=f"Tự động xuất đồ uống bán POS (Seed {today.strftime('%d/%m/%Y')})"
        )

    # ─────────────────────────────────────────────────────────────
    # XÓA DỮ LIỆU CŨ CỦA NGÀY NÀY ĐỂ TRÁNH TRÙNG LẶP
    # ─────────────────────────────────────────────────────────────
    HoaDon.objects.filter(thoi_gian_vao__date=today).delete()
    
    # ─────────────────────────────────────────────────────────────
    # CHỈ 2 PHƯƠNG THỨC KHỚP VỚI MÁY POS THỰC TẾ
    #   70% Tiền mặt  |  30% Chuyển khoản QR
    # ─────────────────────────────────────────────────────────────
    PAYMENT_METHODS = ['tien_mat', 'chuyen_khoan']
    PAYMENT_WEIGHTS = [0.70,       0.30]
    
    # Phân bổ giờ trong ngày (buffet trưa + tối). Giới hạn tối đa nhận khách là 20:30
    HOUR_CHOICES = [11, 12, 13, 17, 18, 19, 20]
    HOUR_WEIGHTS = [0.08, 0.22, 0.10, 0.05, 0.15, 0.25, 0.15]
    
    GROUP_CHOICES = [2, 4, 6, 8, 10]
    GROUP_WEIGHTS = [0.30, 0.35, 0.20, 0.10, 0.05]
    
    rng = random.Random()  # Ngẫu nhiên thực sự mỗi lần bấm
    
    # Số lượng khách theo ngày cuối tuần hay ngày thường
    is_weekend = today.weekday() >= 4  # Thứ 6, 7, CN
    num_invoices = rng.randint(60, 80) if is_weekend else rng.randint(40, 55)
    
    # Tắt auto_now_add để set thời gian lịch sử trong ngày
    HoaDon._meta.get_field('thoi_gian_vao').auto_now_add = False
    ChiTietHoaDon._meta.get_field('thoi_gian_order').auto_now_add = False
    
    try:
        setting = None
        try:
            from core.models import SystemSetting
            setting = SystemSetting.objects.get(id=1)
            vat_rate = float(setting.vat_tax or 0) / 100.0
            sc_rate  = float(setting.service_charge or 0) / 100.0
        except Exception:
            vat_rate = 0.08
            sc_rate  = 0.05
        
        for _ in range(num_invoices):
            hour     = rng.choices(HOUR_CHOICES, weights=HOUR_WEIGHTS, k=1)[0]
            
            # Đảm bảo không nhận khách sau 20:30
            if hour == 20:
                minute = rng.randint(0, 30)
            else:
                minute = rng.randint(0, 59)
                
            so_khach = rng.choices(GROUP_CHOICES, weights=GROUP_WEIGHTS, k=1)[0]
            
            checkin_dt = timezone.make_aware(
                dt.datetime(today.year, today.month, today.day,
                            hour, minute, rng.randint(0, 59))
            )
            duration_min = rng.randint(90, 150)
            checkout_dt  = checkin_dt + timedelta(minutes=duration_min)
            
            # Đảm bảo không có hóa đơn nào thanh toán sau 22:30 (Giờ đóng cửa)
            closing_time = timezone.make_aware(dt.datetime(today.year, today.month, today.day, 22, 30, 0))
            if checkout_dt > closing_time:
                checkout_dt = closing_time
                # Tính lại thời lượng để logic chuẩn xác
                duration_min = int((checkout_dt - checkin_dt).total_seconds() / 60)
                if duration_min < 45: # Nếu khách vào quá muộn thì dời giờ vào lên sớm hơn
                    checkin_dt = closing_time - timedelta(minutes=rng.randint(60, 90))
            
            phuong_thuc = rng.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS, k=1)[0]
            khach_hang  = rng.choice(kh_list) if (kh_list and rng.random() < 0.35) else None
            
            # Tiền buffet
            buffet         = rng.choice(buffet_list)
            tien_buffet    = int(buffet.gia_ban) * so_khach
            tong_hang      = tien_buffet
            
            # Tạo hóa đơn (để model tự sinh ma_hoa_don qua save())
            hd = HoaDon(
                ban_an          = rng.choice(ban_list),
                khach_hang      = khach_hang,
                nhan_vien       = request.user,
                thoi_gian_vao   = checkin_dt,
                thoi_gian_ra    = checkout_dt,
                so_khach        = so_khach,
                tong_tien_hang  = 0,   # Cập nhật sau
                chiet_khau      = 0,
                vat_phu_thu     = 0,
                khach_can_tra   = 0,
                phuong_thuc_tt  = phuong_thuc,
                so_tien_thu     = 0,
                ngay_thanh_toan = checkout_dt,
                trang_thai      = 'da_thanh_toan',
                ghi_chu         = 'SEED_HISTORY',
            )
            hd.save()  # Gọi save() để model tự sinh ma_hoa_don = INV-XXXXX
            
            # Chi tiết: Vé buffet
            ChiTietHoaDon.objects.create(
                hoa_don         = hd,
                thuc_don        = buffet,
                ten_mon_luu_tru = buffet.ten_mon,
                don_gia_luu_tru = buffet.gia_ban,
                so_luong        = so_khach,
                thanh_tien      = tien_buffet,
                thoi_gian_order = checkin_dt,
            )
            
            # Chi tiết: Đồ uống (70% khả năng gọi nước)
            if drink_list and rng.random() < 0.70:
                # 80% gọi nước phổ thông (pepsi, aqua), 20% gọi ngẫu nhiên
                if drink_priority and rng.random() < 0.8:
                    drink = rng.choice(drink_priority)
                else:
                    drink = rng.choice(drink_list)
                    
                sl_drink   = rng.randint(1, max(1, so_khach))
                tien_drink = int(drink.gia_ban) * sl_drink
                tong_hang  += tien_drink
                ChiTietHoaDon.objects.create(
                    hoa_don         = hd,
                    thuc_don        = drink,
                    ten_mon_luu_tru = drink.ten_mon,
                    don_gia_luu_tru = drink.gia_ban,
                    so_luong        = sl_drink,
                    thanh_tien      = tien_drink,
                    thoi_gian_order = checkin_dt + timedelta(minutes=rng.randint(5, 20)),
                )
                
                # Trừ kho nguyên liệu đồ uống (Mock Auto-Inventory Deduction)
                if phieu_xuat_do_uong:
                    ten_mon_lower = drink.ten_mon.lower()
                    for nl in nl_list:
                        ten_nl = nl.ten_nguyen_lieu.lower()
                        if len(ten_nl) > 3 and (ten_nl in ten_mon_lower or ten_mon_lower in ten_nl):
                            ChiTietPhieuKho.objects.create(
                                phieu=phieu_xuat_do_uong,
                                nguyen_lieu=nl,
                                so_luong=sl_drink,
                                don_gia=nl.don_gia_trung_binh or 0,
                                thanh_tien=sl_drink * (nl.don_gia_trung_binh or 0)
                            )
                            nl.ton_kho = float(nl.ton_kho) - sl_drink
                            nl.save()
                            break
            
            # Tính lại tổng tiền có VAT + SC
            tien_sc       = tong_hang * sc_rate
            tien_vat      = (tong_hang + tien_sc) * vat_rate
            khach_can_tra = tong_hang + tien_sc + tien_vat
            
            hd.tong_tien_hang = tong_hang
            hd.vat_phu_thu    = round(tien_vat + tien_sc)
            hd.khach_can_tra  = round(khach_can_tra)
            hd.so_tien_thu    = round(khach_can_tra)
            hd.save()
            
            # Cộng điểm VIP nếu có khách hàng
            if khach_hang:
                diem_cong = int(khach_can_tra / 10000)
                if diem_cong > 0:
                    khach_hang.diem_tich_luy = (khach_hang.diem_tich_luy or 0) + diem_cong
                    khach_hang.save()
    
    finally:
        HoaDon._meta.get_field('thoi_gian_vao').auto_now_add = True
        ChiTietHoaDon._meta.get_field('thoi_gian_order').auto_now_add = True
    
    # --- Phiếu Kho (nhập + xuất) ---
    if nl_list and ncc_list:
        # Nhập hàng với số lượng vừa phải để cân bằng với lượng xuất
        for _ in range(rng.randint(1, 2)):
            pn = PhieuKho.objects.create(
                loai_phieu='nhap',
                nha_cung_cap=rng.choice(ncc_list),
                nguoi_thuc_hien=request.user,
                ngay_thuc_hien=timezone.make_aware(dt.datetime.combine(today, dt.time(rng.randint(6, 8), 0))),
                da_thanh_toan=True,
                ghi_chu=f"Nhập kho tự động bổ sung (Seed {today.strftime('%d/%m/%Y')})"
            )
            tong_nhap = 0
            # Nhập ngẫu nhiên 10-20 loại mặt hàng, số lượng 20-60
            selected_nl = rng.sample(list(nl_list), min(len(nl_list), rng.randint(10, 20)))
            for nl in selected_nl:
                sl = rng.randint(20, 60)
                dg = int(nl.don_gia_trung_binh or rng.randint(50000, 200000))
                tt = sl * dg
                ChiTietPhieuKho.objects.create(phieu=pn, nguyen_lieu=nl, so_luong=sl, don_gia=dg, thanh_tien=tt)
                tong_nhap += tt
                nl.ton_kho = float(nl.ton_kho) + sl
                nl.save()
            pn.tong_tien = tong_nhap
            pn.save()
        
        # Thêm nhiều phiếu xuất kho cho bếp
        for i in range(rng.randint(10, 15)):
            px = PhieuKho.objects.create(
                loai_phieu='xuat',
                nguoi_thuc_hien=request.user,
                ngay_thuc_hien=timezone.make_aware(dt.datetime.combine(today, dt.time(rng.randint(8, 20), rng.randint(0, 59)))),
                ghi_chu=f"Xuất phục vụ bếp (Ca {i+1} - Seed {today.strftime('%d/%m/%Y')})"
            )
            for _ in range(rng.randint(10, 25)):
                nl = rng.choice(nl_list)
                sl = round(rng.uniform(1.0, 15.0), 2)
                ChiTietPhieuKho.objects.create(phieu=px, nguyen_lieu=nl, so_luong=sl, don_gia=nl.don_gia_trung_binh or 0, thanh_tien=0)
                nl.ton_kho = max(0, float(nl.ton_kho) - sl)
                nl.save()

        # Thêm 3-5 phiếu xuất hủy (hàng hỏng)
        for i in range(rng.randint(3, 5)):
            px_huy = PhieuKho.objects.create(
                loai_phieu='xuat',
                nguoi_thuc_hien=request.user,
                ngay_thuc_hien=timezone.make_aware(dt.datetime.combine(today, dt.time(rng.randint(14, 22), rng.randint(0, 59)))),
                ghi_chu=f"Xuất hủy nguyên liệu hỏng/hết hạn (Seed {today.strftime('%d/%m/%Y')})"
            )
            for _ in range(rng.randint(3, 8)):
                nl = rng.choice(nl_list)
                sl = round(rng.uniform(0.1, 3.0), 2)
                ChiTietPhieuKho.objects.create(phieu=px_huy, nguyen_lieu=nl, so_luong=sl, don_gia=nl.don_gia_trung_binh or 0, thanh_tien=0)
                nl.ton_kho = max(0, float(nl.ton_kho) - sl)
                nl.save()
    
    return num_invoices
