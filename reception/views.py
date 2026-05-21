import csv
import json
import re
from datetime import timedelta
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt 
from django.db import transaction

# --- IMPORT CÁC MODEL CHÍNH CỦA APP NÀY ---
from .models import KhachHang, KhuVuc, BanAn, PhieuDatBan, PhienSuDungBan

# --- IMPORT BỔ SUNG ĐỂ TRANG QUẢN LÝ BÀN TỰ THAO TÁC HÓA ĐƠN ---
from pos.models import HoaDon, ChiTietHoaDon
from core.models import SystemSetting


# ======================================================================
# 🔥 HÀM TỰ LÀM SẠCH (SELF-HEALING) - CHỐNG TREO TRẠNG THÁI BÀN
# ======================================================================
def cleanup_zombie_tables():
    """ Quét và ép bàn về 'trong' nếu bàn đang treo trạng thái mà không có đơn/hóa đơn thực """
    # 1. Bàn đang báo 'Đã đặt' nhưng thực tế không có phiếu đặt bàn nào gắn với nó
    active_booking_ban_ids = PhieuDatBan.objects.filter(trang_thai='da_xac_nhan').values_list('ban_id', flat=True)
    BanAn.objects.filter(trang_thai='da_dat').exclude(id__in=active_booking_ban_ids).update(trang_thai='trong')

    # 2. Bàn đang báo 'Đang phục vụ/Chờ thanh toán' nhưng thực tế POS không có Hóa đơn nào
    active_invoice_ban_ids = HoaDon.objects.filter(trang_thai='dang_phuc_vu').values_list('ban_an_id', flat=True)
    BanAn.objects.filter(trang_thai__in=['dang_an', 'cho_thanh_toan']).exclude(id__in=active_invoice_ban_ids).update(trang_thai='trong')


# ======================================================================
# 🔥 HÀM TỰ ĐỘNG HỦY ĐẶT BÀN QUÁ GIỜ (DỰA THEO CÀI ĐẶT HỆ THỐNG)
# ======================================================================
def auto_cancel_expired_bookings():
    """ Tự động quét và Hủy các đơn đặt bàn quá thời gian giữ bàn quy định """
    try:
        setting = SystemSetting.objects.filter(id=1).first()
        hold_time = int(setting.hold_table_time) if (setting and setting.hold_table_time) else 15
    except:
        hold_time = 15
        
    thoi_gian_hien_tai = timezone.now()
    thoi_gian_gioi_han = thoi_gian_hien_tai - timedelta(minutes=hold_time)
    
    don_qua_han = PhieuDatBan.objects.filter(
        trang_thai__in=['cho_xac_nhan', 'da_xac_nhan'],
        thoi_gian_den__lt=thoi_gian_gioi_han
    )
    
    if don_qua_han.exists():
        for phieu in don_qua_han:
            with transaction.atomic():
                if phieu.ban:
                    reset_dat_ban_khi_don_ban(phieu.ban)
                
                phieu.trang_thai = 'huy'
                phieu.ghi_chu = (phieu.ghi_chu or "") + f" \n[Hệ thống tự động hủy do khách đến muộn quá {hold_time} phút]"
                phieu.save()


# ======================================================================
# 🔥 HÀM BẢO VỆ ĐỒNG BỘ: TỰ ĐỘNG GỠ PHIẾU ĐẶT BÀN KHI BÀN BỊ ĐỔI VỀ TRỐNG
# ======================================================================
def reset_dat_ban_khi_don_ban(ban_obj):
    with transaction.atomic():
        # 1. Gỡ phiếu đặt bàn
        PhieuDatBan.objects.filter(ban=ban_obj).exclude(trang_thai__in=['hoan_thanh', 'huy']).update(ban=None, trang_thai='cho_xac_nhan')
        
        # 2. Hủy các hóa đơn treo đang dang_phuc_vu của bàn này (để POS xóa màu)
        HoaDon.objects.filter(ban_an=ban_obj, trang_thai='dang_phuc_vu').update(trang_thai='da_huy')
        
        # 3. Đóng các phiên sử dụng bàn
        PhienSuDungBan.objects.filter(ban=ban_obj, trang_thai='dang_phuc_vu').update(trang_thai='huy', thoi_gian_ra=timezone.now())

        # 4. Giải phóng bàn ghép trong ghi chú
        phieus_ghep = PhieuDatBan.objects.filter(ghi_chu__icontains=ban_obj.ten_ban).exclude(trang_thai__in=['hoan_thanh', 'huy'])
        for p in phieus_ghep:
            p.ban = None
            p.trang_thai = 'cho_xac_nhan'
            p.ghi_chu = re.sub(r'\[Hệ thống\].*ghép các bàn:.*', '', p.ghi_chu or '').strip()
            p.save()


# ==========================================
# 1. QUẢN LÝ SƠ ĐỒ BÀN (Tương ứng file tables.html)
# ==========================================
@login_required(login_url='login')
def tables_view(request):
    # CHẠY QUÉT TỰ ĐỘNG HỦY VÀ LÀM SẠCH RÁC TRƯỚC KHI LOAD DỮ LIỆU
    auto_cancel_expired_bookings()
    cleanup_zombie_tables()

    if request.method == 'POST':
        action = request.POST.get('action')
        table_id = request.POST.get('table_id')
        
        # --- ĐOẠN ĐỔI TRẠNG THÁI NHANH TỪ GIAO DIỆN ---
        if action == 'quick_change_status':
            new_status = request.POST.get('new_status', '').strip().lower()
            try:
                ban = get_object_or_404(BanAn, id=table_id)
                ten_ban_cu = ban.ten_ban
                
                with transaction.atomic():
                    # NẾU TRẢ VỀ BÀN TRỐNG -> ĐÁ PHIẾU ĐẶT BÀN VÀ XÓA HÓA ĐƠN TREO
                    if new_status == 'trong':
                        reset_dat_ban_khi_don_ban(ban)
                    
                    ban.trang_thai = new_status
                    ban.save()
                    
                    # TỰ ĐỘNG TẠO HÓA ĐƠN RỖNG KHI LỄ TÂN CHỦ ĐỘNG MỞ BÀN -> POS HIỆN MÀU TÍM
                    if new_status == 'dang_an':
                        HoaDon.objects.get_or_create(
                            ban_an=ban,
                            trang_thai='dang_phuc_vu',
                            defaults={
                                'nhan_vien': request.user,
                                'thoi_gian_vao': timezone.now()
                            }
                        )
                
                stt_text = {
                    'trong': 'Bàn Trống',
                    'dang_an': 'Đang Phục vụ',
                    'da_dat': 'Đã Đặt trước',
                    'cho_thanh_toan': 'Chờ Thanh Toán'
                }.get(new_status, new_status)
                
                messages.success(request, f"Đã chuyển {ten_ban_cu} sang: {stt_text}!")
            except Exception as e:
                messages.error(request, f"Lỗi cập nhật trạng thái: {str(e)}")
            return redirect('tables')

        # --- XÓA MỀM BÀN (SOFT DELETE) ---
        if action == 'delete' and table_id:
            if not request.user.is_superuser:
                messages.error(request, "Lỗi bảo mật: Chỉ Admin hệ thống mới được phép xóa sơ đồ bàn!")
                return redirect('tables')

            ban = get_object_or_404(BanAn, id=table_id)
            if ban.trang_thai in ['dang_an', 'cho_thanh_toan']:
                messages.error(request, f"Không thể xóa {ban.ten_ban} vì đang có khách!")
            else:
                with transaction.atomic():
                    reset_dat_ban_khi_don_ban(ban)
                    ban.trang_thai = 'da_xoa' 
                    ban.save()
                messages.success(request, f"Đã xóa bàn {ban.ten_ban} khỏi hệ thống (Xóa mềm)!")
            return redirect('tables')
            
        # --- THÊM / SỬA BÀN BẰNG FORM CHÍNH ---
        else:
            ten_ban = request.POST.get('ten_ban')
            so_ghe = request.POST.get('so_ghe', 4)
            khu_vuc_id = request.POST.get('khu_vuc')
            khu_vuc_obj = get_object_or_404(KhuVuc, id=khu_vuc_id) if khu_vuc_id else None
            trang_thai = request.POST.get('trang_thai', 'trong').strip().lower()

            if action == 'add' and ten_ban and khu_vuc_obj:
                BanAn.objects.create(
                    ten_ban=ten_ban, so_ghe=so_ghe, 
                    khu_vuc=khu_vuc_obj, trang_thai='trong'
                )
                messages.success(request, "Thêm bàn mới thành công!")
                
            elif action == 'edit' and table_id:
                ban = get_object_or_404(BanAn, id=table_id)
                with transaction.atomic():
                    ban.ten_ban = ten_ban
                    ban.so_ghe = so_ghe
                    ban.khu_vuc = khu_vuc_obj
                    
                    if trang_thai == 'trong':
                        reset_dat_ban_khi_don_ban(ban)
                        
                    ban.trang_thai = trang_thai
                    ban.save()
                    
                    # Đẻ hóa đơn nếu chuyển sang đang ăn
                    if trang_thai == 'dang_an':
                        HoaDon.objects.get_or_create(
                            ban_an=ban, trang_thai='dang_phuc_vu',
                            defaults={'nhan_vien': request.user, 'thoi_gian_vao': timezone.now()}
                        )
                messages.success(request, "Cập nhật thông tin bàn thành công!")

        return redirect('tables') 

    # --- LẤY DATA CHO SƠ ĐỒ BÀN (LỌC BỎ CÁC BÀN ĐÃ XÓA MỀM) ---
    danh_sach_ban_thobe = list(BanAn.objects.exclude(trang_thai='da_xoa').select_related('khu_vuc').all())
    
    def natural_sort_key(ban):
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', ban.ten_ban)]
    danh_sach_ban_thobe.sort(key=natural_sort_key)
    
    # ==========================================================
    # TỐI ƯU MAPPING BẰNG SELECT_RELATED CHỐNG LỖI N+1 QUERY
    # ==========================================================
    active_hds = {hd.ban_an_id: hd for hd in HoaDon.objects.filter(trang_thai='dang_phuc_vu').prefetch_related('chi_tiet')}
    
    active_sessions = PhienSuDungBan.objects.filter(trang_thai='dang_phuc_vu').select_related('khach_hang', 'phieu_dat')
    session_map_id = {s.ban_id: s for s in active_sessions if s.ban_id}
    session_map_name = {}
    for s in active_sessions:
        if s.phieu_dat and s.phieu_dat.ghi_chu:
            match = re.search(r'ghép các bàn:\s*([^\n]+)', s.phieu_dat.ghi_chu, re.IGNORECASE)
            if match:
                for tb in match.group(1).split(","):
                    session_map_name[tb.strip()] = s

    active_bookings = PhieuDatBan.objects.filter(trang_thai='da_xac_nhan').select_related('khach_hang')
    booking_map_id = {b.ban_id: b for b in active_bookings if b.ban_id}
    booking_map_name = {}
    for b in active_bookings:
        if b.ghi_chu:
            match = re.search(r'ghép các bàn:\s*([^\n]+)', b.ghi_chu, re.IGNORECASE)
            if match:
                for tb in match.group(1).split(","):
                    booking_map_name[tb.strip()] = b

    danh_sach_khu_vuc = KhuVuc.objects.all().order_by('id')
    ban_theo_khu_vuc = {}
    
    for ban in danh_sach_ban_thobe:
        ban.kh_ten = ""
        ban.kh_adults = ""
        ban.kh_children = ""
        ban.kh_time = ""
        ban.kh_sdt = ""
        ban.kh_ghi_chu = ""
        ban.is_doan = False
        
        # Mapping Trạng thái hiển thị (Màu Tím Chờ Phục Vụ)
        hd = active_hds.get(ban.id)
        if hd:
            if ban.trang_thai == 'cho_thanh_toan':
                ban.trang_thai_hien_thi = 'cho_thanh_toan'
            else:
                ban.trang_thai_hien_thi = 'dang_phuc_vu' if hd.chi_tiet.exists() else 'cho_phuc_vu'
        else:
            ban.trang_thai_hien_thi = 'cho_phuc_vu' if ban.trang_thai == 'dang_an' else ban.trang_thai

        # Mapping bàn Đang Ăn
        if ban.trang_thai_hien_thi in ['dang_phuc_vu', 'cho_phuc_vu', 'cho_thanh_toan']:
            session = session_map_id.get(ban.id) or session_map_name.get(ban.ten_ban)
            if session:
                ban.kh_ten = session.khach_hang.ho_ten
                ban.kh_sdt = session.khach_hang.so_dien_thoai
                if session.phieu_dat:
                    ban.kh_adults = session.phieu_dat.so_nguoi
                    ban.kh_children = session.phieu_dat.so_tre_em or 0
                    ban.kh_time = session.phieu_dat.thoi_gian_den.strftime('%H:%M %d/%m')
                    ban.kh_ghi_chu = session.phieu_dat.ghi_chu
                    if session.phieu_dat.ghi_chu and "ghép các bàn:" in session.phieu_dat.ghi_chu.lower():
                        ban.is_doan = True
                else:
                    ban.kh_adults = session.so_khach_thuc_te
                    ban.kh_children = 0
                    ban.kh_time = "Walk-in"
                    
        # Mapping bàn Đã Đặt
        elif ban.trang_thai_hien_thi == 'da_dat':
            booking = booking_map_id.get(ban.id) or booking_map_name.get(ban.ten_ban)
            if booking:
                ban.kh_ten = booking.khach_hang.ho_ten
                ban.kh_sdt = booking.khach_hang.so_dien_thoai
                ban.kh_adults = booking.so_nguoi
                ban.kh_children = booking.so_tre_em or 0
                ban.kh_time = booking.thoi_gian_den.strftime('%H:%M %d/%m')
                ban.kh_ghi_chu = booking.ghi_chu
                if booking.ghi_chu and "ghép các bàn:" in booking.ghi_chu.lower():
                    ban.is_doan = True

        if ban.khu_vuc not in ban_theo_khu_vuc:
            ban_theo_khu_vuc[ban.khu_vuc] = []
        ban_theo_khu_vuc[ban.khu_vuc].append(ban)

    tat_ca_ban = BanAn.objects.exclude(trang_thai='da_xoa')
    context = {
        'ban_theo_khu_vuc': ban_theo_khu_vuc, 
        'danh_sach_khu_vuc': danh_sach_khu_vuc,
        'tat_ca_ban': tat_ca_ban,
        'ban_trong': tat_ca_ban.filter(trang_thai='trong').count(),
        'dang_phuc_vu': sum(1 for b in danh_sach_ban_thobe if b.trang_thai_hien_thi == 'dang_phuc_vu'),
        'cho_phuc_vu': sum(1 for b in danh_sach_ban_thobe if b.trang_thai_hien_thi == 'cho_phuc_vu'),
        'da_dat': tat_ca_ban.filter(trang_thai='da_dat').count(),
    }
    return render(request, 'customers/tables.html', context)

# ==========================================
# 2. QUẢN LÝ KHU VỰC (Zone)
# ==========================================
@login_required(login_url='login')
def table_zones_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        zone_id = request.POST.get('zone_id')
        
        if action == 'delete' and zone_id:
            zone = get_object_or_404(KhuVuc, id=zone_id)
            zone.delete()
            messages.success(request, "Đã xóa khu vực thành công!")
        else:
            ten_khu_vuc = request.POST.get('ten_khu_vuc')
            if action == 'add':
                KhuVuc.objects.create(ten_khu_vuc=ten_khu_vuc)
                messages.success(request, "Thêm khu vực mới thành công!")
            elif action == 'edit' and zone_id:
                zone = get_object_or_404(KhuVuc, id=zone_id)
                zone.ten_khu_vuc = ten_khu_vuc
                zone.save()
                messages.success(request, "Cập nhật khu vực thành công!")
        return redirect('table_zones')

    danh_sach_khu_vuc = KhuVuc.objects.all().order_by('id')
    zone_data = [{'obj': kv,'tong_ban': kv.danh_sach_ban.exclude(trang_thai='da_xoa').count()} for kv in danh_sach_khu_vuc]

    context = {
        'zone_data': zone_data,
        'tong_khu_vuc': danh_sach_khu_vuc.count()
    }
    return render(request, 'customers/table_zones.html', context)

# ==========================================
# 3. CHỨC NĂNG XUẤT/NHẬP KHÁCH HÀNG (CSV)
# ==========================================
@login_required(login_url='login')
def export_customers_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Danh_sach_khach_hang.csv"'
    response.write('\ufeff'.encode('utf8')) 
    writer = csv.writer(response)
    writer.writerow(['Họ và tên', 'Số điện thoại', 'Ngày sinh', 'Điểm tích lũy'])
    for kh in KhachHang.objects.all():
        writer.writerow([kh.ho_ten, kh.so_dien_thoai, kh.ngay_sinh, kh.diem_tich_luy])
    return response

@login_required(login_url='login')
def import_customers_csv(request):
    if request.method == 'POST' and request.FILES.get('file_csv'):
        file = request.FILES['file_csv']
        try:
            decoded_file = file.read().decode('utf-8').splitlines()
            reader = csv.reader(decoded_file)
            next(reader, None) 
            count = 0
            with transaction.atomic():
                for row in reader:
                    if len(row) >= 2:
                        KhachHang.objects.update_or_create(
                            so_dien_thoai=row[1].strip(),
                            defaults={'ho_ten': row[0].strip(), 'diem_tich_luy': 0}
                        )
                        count += 1
            messages.success(request, f"Đã Import thành công {count} khách hàng!")
        except Exception as e:
            messages.error(request, f"Lỗi Import: {str(e)}")
    return redirect('customers')


# ==============================================================
# 4. QUẢN LÝ ĐẶT BÀN (Booking) VÀ LUỒNG XẾP BÀN
# ==============================================================
@login_required(login_url='login')
def booking_list(request):
    auto_cancel_expired_bookings()
    cleanup_zombie_tables()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        booking_id = request.POST.get('booking_id')
        
        # --- XỬ LÝ CHECK-IN NHẬN BÀN NHÓM ---
        if action == 'checkin' and booking_id:
            try:
                with transaction.atomic():
                    phieu = get_object_or_404(PhieuDatBan, id=booking_id)
                    ban_chinh = phieu.ban
                    
                    if not ban_chinh:
                        messages.error(request, "Phiếu này chưa được xếp bàn!")
                    else:
                        phieu.trang_thai = 'hoan_thanh'
                        phieu.save()
                        
                        table_names = [ban_chinh.ten_ban]
                        if phieu.ghi_chu:
                            match = re.search(r'ghép các bàn:\s*([^\n]+)', phieu.ghi_chu, re.IGNORECASE)
                            if match:
                                table_names.extend([t.strip() for t in match.group(1).split(',')])
                        
                        bans = BanAn.objects.filter(ten_ban__in=table_names)
                        bans.update(trang_thai='dang_an')
                        
                        tong_khach = phieu.so_nguoi + (phieu.so_tre_em if phieu.so_tre_em else 0)
                        PhienSuDungBan.objects.create(
                            ban=ban_chinh, khach_hang=phieu.khach_hang, phieu_dat=phieu,
                            so_khach_thuc_te=tong_khach, trang_thai='dang_phuc_vu'
                        )
                        
                        # TẠO ĐỒNG LOẠT HÓA ĐƠN RỖNG CHO TẤT CẢ CÁC BÀN VỪA NHẬN
                        for b in bans:
                            HoaDon.objects.get_or_create(
                                ban_an=b,
                                trang_thai='dang_phuc_vu',
                                defaults={
                                    'khach_hang': phieu.khach_hang,
                                    'nhan_vien': request.user,
                                    'thoi_gian_vao': timezone.now(),
                                    'so_khach': tong_khach
                                }
                            )

                        messages.success(request, f"Khách đã nhận bàn! Đã đồng bộ sang POS (Màu tím).")
            except Exception as e:
                messages.error(request, f"Lỗi Check-in: {str(e)}")
            return redirect('bookings')

        # --- XÓA PHIẾU ---
        if action == 'delete' and booking_id:
            phieu = get_object_or_404(PhieuDatBan, id=booking_id)
            if phieu.ban and phieu.trang_thai in ['da_xac_nhan', 'cho_xac_nhan']:
                with transaction.atomic():
                    ban = phieu.ban
                    reset_dat_ban_khi_don_ban(ban)
            phieu.delete()
            messages.success(request, "Đã xóa phiếu đặt bàn!")
            return redirect('bookings')
            
        # --- THÊM VÀ SỬA PHIẾU ---
        else:
            ten_kh = request.POST.get('ten_khach_hang')
            sdt = request.POST.get('so_dien_thoai')
            thoi_gian_den = request.POST.get('thoi_gian_den')
            so_nguoi = request.POST.get('so_nguoi', 1)
            so_tre_em = request.POST.get('so_tre_em', 0) 
            ghi_chu = request.POST.get('ghi_chu', '')
            trang_thai = request.POST.get('trang_thai', 'cho_xac_nhan')

            if action in ['add', 'edit']: 
                try:
                    with transaction.atomic(): 
                        # Kiểm tra khách hàng đã tồn tại chưa
                        khach_obj = KhachHang.objects.filter(so_dien_thoai=sdt).first()

                        if khach_obj:
                            # Nếu đã tồn tại -> cập nhật tên nếu khác
                            if ten_kh and khach_obj.ho_ten != ten_kh:
                                khach_obj.ho_ten = ten_kh
                                khach_obj.save()
                        else:
                            # Nếu chưa có -> tạo mới
                            khach_obj = KhachHang.objects.create(
                                ho_ten=ten_kh,
                                so_dien_thoai=sdt,
                                diem_tich_luy=0
                            )

                        if action == 'add':
                            new_booking = PhieuDatBan.objects.create(
                                khach_hang=khach_obj, thoi_gian_den=thoi_gian_den,
                                so_nguoi=so_nguoi, so_tre_em=so_tre_em,
                                ghi_chu=ghi_chu, trang_thai='cho_xac_nhan' 
                            )
                            messages.success(request, "Đã lưu phiếu! Vui lòng chọn bàn cho khách.")
                            return redirect(f"{request.path}?auto_map={new_booking.id}")
                            
                        elif action == 'edit' and booking_id:
                            phieu = get_object_or_404(PhieuDatBan, id=booking_id)
                            phieu.khach_hang = khach_obj
                            phieu.thoi_gian_den = thoi_gian_den
                            phieu.so_nguoi = so_nguoi
                            phieu.so_tre_em = so_tre_em
                            phieu.ghi_chu = ghi_chu
                            phieu.trang_thai = trang_thai
                            phieu.save()
                            messages.success(request, "Cập nhật phiếu đặt bàn thành công!")
                except Exception as e:
                    messages.error(request, f"Lỗi hệ thống: {str(e)}")
            
            return redirect('bookings')

    today = timezone.now().date()
    danh_sach_dat_ban = PhieuDatBan.objects.select_related('khach_hang', 'ban').filter(thoi_gian_den__date__gte=today).order_by('thoi_gian_den')
    
    context = {
        'danh_sach_dat_ban': danh_sach_dat_ban,
        'tong_booking': danh_sach_dat_ban.count(),
        'khach_du_kien': sum(p.so_nguoi + (p.so_tre_em or 0) for p in danh_sach_dat_ban if p.trang_thai != 'huy'),
        'da_nhan_ban': danh_sach_dat_ban.filter(trang_thai='hoan_thanh').count(),
        'da_huy': danh_sach_dat_ban.filter(trang_thai='huy').count(),
    }
    return render(request, 'customers/bookings.html', context)


# ==========================================
# 5. API GÁN BÀN TỪ GIAO DIỆN SƠ ĐỒ BÀN
# ==========================================
@login_required(login_url='login')
@require_POST
def api_assign_table(request):
    try:
        data = json.loads(request.body)
        booking_id = data.get('booking_id')
        table_ids = data.get('table_ids', []) 

        if not table_ids:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng chọn ít nhất 1 bàn!'})

        with transaction.atomic():
            phieu = get_object_or_404(PhieuDatBan, id=booking_id)
            
            if phieu.ban:
                reset_dat_ban_khi_don_ban(phieu.ban)

            ban_chinh = get_object_or_404(BanAn, id=table_ids[0])
            phieu.ban = ban_chinh
            phieu.trang_thai = 'da_xac_nhan' 
            
            if len(table_ids) > 1:
                danh_sach_ten_ban = list(BanAn.objects.filter(id__in=table_ids).values_list('ten_ban', flat=True))
                chuoi_ten_ban = ", ".join(danh_sach_ten_ban)
                ghi_chu_cu = phieu.ghi_chu or ""
                ghi_chu_cu = re.sub(r'\[Hệ thống\].*ghép các bàn:.*', '', ghi_chu_cu).strip()
                phieu.ghi_chu = f"{ghi_chu_cu}\n[Hệ thống] Đoàn khách ngồi ghép các bàn: {chuoi_ten_ban}".strip()
                
            phieu.save()
            BanAn.objects.filter(id__in=table_ids).update(trang_thai='da_dat')

        return JsonResponse({'status': 'success', 'message': 'Xếp bàn thành công!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

# ==========================================
# 6. CÁC API AJAX HỖ TRỢ KHÁC 
# ==========================================
@login_required(login_url='login')
def get_available_tables_ajax(request):
    try:
        ban_trong = sorted(
            BanAn.objects.filter(
                trang_thai='trong'
            ).select_related('khu_vuc'),
            key=lambda b: int(re.search(r'\d+', b.ten_ban).group()) 
            if re.search(r'\d+', b.ten_ban) else 999
        )

        data = [{
            'id': b.id,
            'ten_ban': b.ten_ban,
            'so_ghe': b.so_ghe,
            'khu_vuc': b.khu_vuc.ten_khu_vuc if b.khu_vuc else "Chung"
        } for b in ban_trong]

        return JsonResponse({
            'status': 'success',
            'tables': data
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required(login_url='login')
def clear_table_ajax(request, ban_id):
    try:
        ban = get_object_or_404(BanAn, id=ban_id)
        with transaction.atomic():
            reset_dat_ban_khi_don_ban(ban)
            ban.trang_thai = 'trong'
            ban.save()
        return JsonResponse({'status': 'success', 'message': f'Đã dọn xong {ban.ten_ban}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='login')
@require_POST
def update_booking_status_ajax(request, pk):
    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        phieu = get_object_or_404(PhieuDatBan, id=pk)
        
        with transaction.atomic():
            phieu.trang_thai = new_status
            if new_status == 'hoan_thanh' and phieu.ban:
                phieu.ban.trang_thai = 'dang_an'
                phieu.ban.save()
                
                tong_khach = phieu.so_nguoi + (phieu.so_tre_em if phieu.so_tre_em else 0)
                HoaDon.objects.get_or_create(
                    ban_an=phieu.ban,
                    trang_thai='dang_phuc_vu',
                    defaults={
                        'khach_hang': phieu.khach_hang,
                        'nhan_vien': request.user,
                        'thoi_gian_vao': timezone.now(),
                        'so_khach': tong_khach
                    }
                )
                
            phieu.save()
        return JsonResponse({'status': 'success', 'message': 'Cập nhật thành công!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt 
def api_book_table(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            with transaction.atomic():
                khach_hang, _ = KhachHang.objects.get_or_create(
                    so_dien_thoai=data.get('phone'),
                    defaults={'ho_ten': data.get('name'), 'diem_tich_luy': 0}
                )
                PhieuDatBan.objects.create(
                    khach_hang=khach_hang, thoi_gian_den=f"{data.get('date')} {data.get('time')}",
                    so_nguoi=int(data.get('adults') or 1), so_tre_em=int(data.get('children') or 0),
                    ghi_chu=f"[WEB] Cơ sở: {data.get('branch')}. Lời nhắn: {data.get('note', '')}".strip(),
                    trang_thai='cho_xac_nhan' 
                )
            return JsonResponse({'status': 'success', 'message': 'Đặt bàn thành công!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Chỉ hỗ trợ POST'}, status=405)


# =======================================================================================
# 🔥 TÍCH HỢP TÍNH NĂNG CHUYỂN, GỘP, TÁCH BÀN CỦA QUẢN LÝ (ĐỘC LẬP HOÀN TOÀN VỚI POS)
# =======================================================================================

@login_required
def api_manager_get_order(request, ban_id):
    ban = get_object_or_404(BanAn, id=ban_id)
    hd = HoaDon.objects.filter(ban_an=ban, trang_thai='dang_phuc_vu').first()
    if not hd:
        return JsonResponse({'status': 'error'})
    
    items = [{'id': ct.id, 'ten_mon': ct.ten_mon_luu_tru, 'so_luong': ct.so_luong} for ct in hd.chi_tiet.all()]
    return JsonResponse({'status': 'success', 'hoa_don_id': hd.id, 'items': items})

@login_required
def api_manager_transfer(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hd = get_object_or_404(HoaDon, id=data.get('hoa_don_id'))
            ban_cu = hd.ban_an
            ban_moi = get_object_or_404(BanAn, id=data.get('ban_moi_id'))

            if ban_moi.trang_thai != 'trong':
                return JsonResponse({'status': 'error', 'message': 'Bàn đích đang có khách!'})

            with transaction.atomic():
                # CHUYỂN HÓA ĐƠN
                hd.ban_an = ban_moi
                hd.save()
                # CHUYỂN PHIÊN SỬ DỤNG BÀN
                session = PhienSuDungBan.objects.filter(
                    ban=ban_cu,
                    trang_thai='dang_phuc_vu'
                ).first()
                if session:
                    session.ban = ban_moi
                    session.save()
                # CHUYỂN PHIẾU ĐẶT BÀN
                booking = PhieuDatBan.objects.filter(
                    ban=ban_cu
                ).exclude(
                    trang_thai__in=['huy']
                ).first()
                if booking:
                    booking.ban = ban_moi
                    booking.save()
                # UPDATE TRẠNG THÁI BÀN
                ban_moi.trang_thai = 'dang_an'
                ban_moi.save()
                if ban_cu:
                    ban_cu.trang_thai = 'trong'
                    ban_cu.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def api_manager_merge(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hd_nguon = get_object_or_404(HoaDon, id=data.get('hoa_don_id'))
            ban_dich = get_object_or_404(BanAn, id=data.get('ban_dich_id'))
            hd_dich = HoaDon.objects.filter(ban_an=ban_dich, trang_thai='dang_phuc_vu').first()
            
            if not hd_dich:
                return JsonResponse({'status': 'error', 'message': 'Bàn đích không có hóa đơn để gộp!'})

            try:
                vat_rate = float(SystemSetting.objects.get(id=1).vat_tax)
            except:
                vat_rate = 8.0 

            with transaction.atomic():
                for ct in hd_nguon.chi_tiet.all():
                    ct_dich = hd_dich.chi_tiet.filter(goi_buffet=ct.goi_buffet, do_uong=ct.do_uong, don_gia_luu_tru=ct.don_gia_luu_tru).first()
                    if ct_dich:
                        ct_dich.so_luong += ct.so_luong
                        ct_dich.thanh_tien = ct_dich.so_luong * ct_dich.don_gia_luu_tru
                        ct_dich.save()
                    else:
                        ct.hoa_don = hd_dich
                        ct.save()

                tong = sum(i.thanh_tien for i in hd_dich.chi_tiet.all())
                tien_vat = (float(tong) - float(hd_dich.chiet_khau)) * (vat_rate / 100.0)
                hd_dich.tong_tien_hang = tong
                hd_dich.vat_phu_thu = tien_vat
                hd_dich.khach_can_tra = float(tong) + tien_vat - float(hd_dich.chiet_khau)
                hd_dich.save()

                ban_nguon = hd_nguon.ban_an
                hd_nguon.delete()
                if ban_nguon:
                    ban_nguon.trang_thai = 'trong'
                    ban_nguon.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def api_manager_split(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hd_cu = get_object_or_404(HoaDon, id=data.get('hoa_don_id'))
            ban_moi = get_object_or_404(BanAn, id=data.get('ban_moi_id'))
            items_to_split = data.get('items', [])

            try:
                vat_rate = float(SystemSetting.objects.get(id=1).vat_tax)
            except:
                vat_rate = 8.0 

            with transaction.atomic():
                hd_moi, created = HoaDon.objects.get_or_create(ban_an=ban_moi, trang_thai='dang_phuc_vu', defaults={'nhan_vien': request.user})
                if created or ban_moi.trang_thai == 'trong':
                    ban_moi.trang_thai = 'dang_an'
                    ban_moi.save()

                for item in items_to_split:
                    ct_cu = get_object_or_404(ChiTietHoaDon, id=item.get('ct_id'), hoa_don=hd_cu)
                    qty_move = min(int(item.get('qty_move', 0)), ct_cu.so_luong)
                    if qty_move <= 0: continue

                    ct_cu.so_luong -= qty_move
                    ct_cu.thanh_tien = ct_cu.so_luong * ct_cu.don_gia_luu_tru
                    if ct_cu.so_luong <= 0: ct_cu.delete()
                    else: ct_cu.save()

                    ct_moi = ChiTietHoaDon.objects.filter(hoa_don=hd_moi, goi_buffet=ct_cu.goi_buffet, do_uong=ct_cu.do_uong, don_gia_luu_tru=ct_cu.don_gia_luu_tru).first()
                    if ct_moi:
                        ct_moi.so_luong += qty_move
                        ct_moi.thanh_tien = ct_moi.so_luong * ct_moi.don_gia_luu_tru
                        ct_moi.save()
                    else:
                        ChiTietHoaDon.objects.create(hoa_don=hd_moi, goi_buffet=ct_cu.goi_buffet, do_uong=ct_cu.do_uong, ten_mon_luu_tru=ct_cu.ten_mon_luu_tru, don_gia_luu_tru=ct_cu.don_gia_luu_tru, so_luong=qty_move, thanh_tien=qty_move * ct_cu.don_gia_luu_tru)

                for hd in [hd_cu, hd_moi]:
                    if hd.chi_tiet.count() == 0:
                        ban = hd.ban_an
                        hd.delete()
                        if ban:
                            ban.trang_thai = 'trong'
                            ban.save()
                    else:
                        tong = sum(i.thanh_tien for i in hd.chi_tiet.all())
                        tien_vat = (float(tong) - float(hd.chiet_khau)) * (vat_rate / 100.0)
                        hd.tong_tien_hang = tong
                        hd.vat_phu_thu = tien_vat
                        hd.khach_can_tra = float(tong) + tien_vat - float(hd.chiet_khau)
                        hd.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
# ==========================================
# API GỢI Ý KHÁCH HÀNG THEO SĐT
# ==========================================
@login_required(login_url='login')
def search_customer(request):

    q = request.GET.get('q', '')

    customers = KhachHang.objects.filter(
        so_dien_thoai__icontains=q
    )[:10]

    data = []

    for kh in customers:
        data.append({
            'id': kh.id,
            'ho_ten': kh.ho_ten,
            'so_dien_thoai': kh.so_dien_thoai
        })

    return JsonResponse(data, safe=False)

