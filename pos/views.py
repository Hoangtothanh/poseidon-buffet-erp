import csv
import json
import re
import traceback
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from django.db import transaction 
from customers.views import ai_goi_y_voucher 
from django.views.decorators.http import require_POST

# --- IMPORT MODEL ---
# Lưu ý: Điều chỉnh tên app (core, reception, menu) cho khớp với project của bạn
from .models import HoaDon, ChiTietHoaDon, ThanhToan
from reception.models import BanAn, KhachHang
from menu.models import GoiBuffet, DoUongDichVu
from core.models import SystemSetting 

# ==========================================
# 1. MÀN HÌNH BÁN HÀNG (POS THU NGÂN SPA)
# ==========================================
@login_required(login_url='login')
def pos_view(request):
    try:
        goi_buffet = GoiBuffet.objects.filter(hien_thi_pos=True) 
        do_uong = DoUongDichVu.objects.filter(hien_thi_pos=True, con_hang=True)
    except:
        goi_buffet = GoiBuffet.objects.all()
        do_uong = DoUongDichVu.objects.all()

    # KIỂM TRA PHÂN QUYỀN: Thu ngân vs Nhân viên Order
    is_cashier = request.user.is_superuser or request.user.groups.filter(name__icontains='thu ngân').exists()

    # LẤY MỨC VAT VÀ CẤU HÌNH NGÂN HÀNG TỪ CÀI ĐẶT HỆ THỐNG
    try:
        setting = SystemSetting.objects.get(id=1)
        vat_rate = float(setting.vat_tax) if setting.vat_tax else 0.0
    except:
        setting = None
        vat_rate = 8.0 

    context = {
        'goi_buffet': goi_buffet,
        'do_uong': do_uong,
        'is_cashier': is_cashier,
        'vat_rate': vat_rate,
        'setting': setting, # Đẩy toàn bộ object setting ra để lấy bank_id, bank_account_no...
    }
    return render(request, 'pos/pos.html', context)


# ==========================================
# 2. XỬ LÝ THANH TOÁN (PAYMENTS LIST - BACKEND CŨ)
# ==========================================
@login_required(login_url='login')
def payments_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        bill_id = request.POST.get('bill_id')
        method = request.POST.get('method', 'tien_mat')
        
        if action == 'pay' and bill_id:
            hd = get_object_or_404(HoaDon, id=bill_id)
            
            ThanhToan.objects.create(
                hoa_don=hd,
                phuong_thuc=method,
                so_tien_thu=hd.khach_can_tra,
                nhan_vien_thu=request.user
            )
            
            hd.trang_thai = 'da_thanh_toan'
            hd.thoi_gian_ra = timezone.now()
            
            if hd.ban_an:
                hd.ban_an.trang_thai = 'trong'
                hd.ban_an.save()
                
            hd.save()
            messages.success(request, f"Đã thanh toán thành công {hd.ma_hoa_don}!")
            return redirect('/pos/payments/')

    danh_sach_hoa_don = HoaDon.objects.all().order_by('-thoi_gian_vao')
    today = timezone.now().date()
    open_bills_count = HoaDon.objects.filter(trang_thai='dang_phuc_vu').count()
    paid_bills_count = HoaDon.objects.filter(trang_thai='da_thanh_toan', thoi_gian_vao__date=today).count()
    
    context = {
        'danh_sach_hoa_don': danh_sach_hoa_don,
        'open_bills_count': open_bills_count,
        'paid_bills_count': paid_bills_count,
    }
    return render(request, 'pos/payments.html', context)


# ==========================================
# 3. LỊCH SỬ HÓA ĐƠN (INVOICE LIST)
# ==========================================
@login_required(login_url='login')
def invoice_list(request):
    danh_sach_hoa_don = HoaDon.objects.filter(trang_thai='da_thanh_toan').order_by('-thoi_gian_ra')
    
    total_txns = danh_sach_hoa_don.count()
    total_revenue = sum(hd.khach_can_tra for hd in danh_sach_hoa_don)
    total_card_bank = 0
    
    for hd in danh_sach_hoa_don:
        first_payment = hd.thanh_toan.first()
        if first_payment and first_payment.phuong_thuc != 'tien_mat':
            total_card_bank += first_payment.so_tien_thu
            
    context = {
        'danh_sach_hoa_don': danh_sach_hoa_don,
        'total_txns': total_txns,
        'total_revenue': total_revenue,
        'total_card_bank': total_card_bank,
    }
    return render(request, 'pos/invoices.html', context)


# ==========================================
# 4. AJAX: LẤY CHI TIẾT HÓA ĐƠN Ở BẢNG QUẢN TRỊ
# ==========================================
@login_required(login_url='login')
def invoice_detail_ajax(request, pk):
    try:
        hd = get_object_or_404(HoaDon, id=pk)
        items_data = [{
            'ten_mon': item.ten_mon_luu_tru,
            'so_luong': item.so_luong,
            'don_gia': float(item.don_gia_luu_tru),
            'thanh_tien': float(item.thanh_tien)
        } for item in hd.chi_tiet.all()]

        return JsonResponse({
            'status': 'success',
            'ma_hoa_don': hd.ma_hoa_don,
            'ten_ban': hd.ban_an.ten_ban if hd.ban_an else 'Mang đi',
            'thoi_gian_vao': hd.thoi_gian_vao.strftime("%H:%M - %d/%m/%Y"),
            'tong_tien_hang': float(hd.tong_tien_hang),
            'chiet_khau': float(hd.chiet_khau),
            'vat_phu_thu': float(hd.vat_phu_thu),
            'khach_can_tra': float(hd.khach_can_tra),
            'items': items_data
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

# ==========================================
# 5. MÀN HÌNH MENU KHÁCH HÀNG & EXCEL
# ==========================================
def customer_menu_view(request):
    """ Hàm render menu QR cho khách (Đã khôi phục) """
    return render(request, 'customers/customer_menu.html')

@login_required(login_url='login')
def export_invoices_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="lich_su_giao_dich_pos.csv"'
    response.write('\ufeff'.encode('utf8'))

    writer = csv.writer(response)
    writer.writerow(['Mã Giao Dịch', 'Mã Hóa Đơn', 'Thời Gian', 'Phương Thức', 'Số Tiền (VND)', 'Nhân Viên Thu'])

    for hd in HoaDon.objects.filter(trang_thai='da_thanh_toan').order_by('-thoi_gian_ra'):
        payment = hd.thanh_toan.last()
        phuong_thuc = payment.get_phuong_thuc_display() if payment else "Tiền mặt"
        ma_gd = f"TXN-{payment.id if payment else hd.id:04d}"
        thoi_gian = hd.thoi_gian_ra.strftime("%Y-%m-%d %H:%M") if hd.thoi_gian_ra else ""
        nhan_vien = payment.nhan_vien_thu.username if (payment and payment.nhan_vien_thu) else (hd.nhan_vien.username if hd.nhan_vien else "Hệ thống")
        writer.writerow([ma_gd, hd.ma_hoa_don, thoi_gian, phuong_thuc, hd.khach_can_tra, nhan_vien])

    return response


# =========================================================================
# PHẦN API DÀNH RIÊNG CHO GIAO DIỆN SPA CỦA BÁN HÀNG TẠI QUẦY (FRONTEND JS)
# =========================================================================

@login_required(login_url='login')
def api_load_tables(request):
    """ API Load sơ đồ bàn phân theo khu vực (Đã bổ sung Sắp xếp chuẩn, Ẩn bàn đã xóa và Trạng thái Chờ thanh toán) """
    try:
        # LÝ DO SỬA: Thay .all() bằng .exclude(trang_thai='da_xoa') để giấu các bàn đã bị xóa mềm
        danh_sach_ban = list(BanAn.objects.exclude(trang_thai='da_xoa').select_related('khu_vuc'))
        
        def natural_sort_key(ban):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', ban.ten_ban)]
        danh_sach_ban.sort(key=natural_sort_key)

        zones_dict = {}
        for ban in danh_sach_ban:
            kv_id = ban.khu_vuc.id if ban.khu_vuc else 0
            kv_ten = ban.khu_vuc.ten_khu_vuc if ban.khu_vuc else "Khu vực chung"
            
            if kv_id not in zones_dict:
                zones_dict[kv_id] = {'khu_vuc_id': kv_id, 'ten_khu_vuc': kv_ten, 'ban_list': []}
                
            hd = HoaDon.objects.filter(ban_an=ban, trang_thai='dang_phuc_vu').first()
            
            # XÁC ĐỊNH TRẠNG THÁI BÀN
            if hd:
                if ban.trang_thai == 'cho_thanh_toan':
                    trang_thai_hien_tai = 'cho_thanh_toan'
                else:
                    # Nếu hóa đơn đã có món -> Đang dùng (Đỏ) | Nếu 0 món -> Chờ phục vụ (Tím)
                    if hd.chi_tiet.exists():
                        trang_thai_hien_tai = 'dang_phuc_vu'
                    else:
                        trang_thai_hien_tai = 'cho_phuc_vu' 
            else:
                trang_thai_hien_tai = ban.trang_thai
            
            # Tính thời gian ngồi
            thoi_gian_ngoi = 0
            if hd and hd.thoi_gian_vao:
                time_diff = timezone.now() - hd.thoi_gian_vao
                thoi_gian_ngoi = int(time_diff.total_seconds() / 60)
            
            zones_dict[kv_id]['ban_list'].append({
                'id': ban.id,
                'ten_ban': ban.ten_ban,
                'so_ghe': getattr(ban, 'so_ghe', 4),
                'trang_thai': trang_thai_hien_tai,
                'tong_tien': float(hd.khach_can_tra) if hd else 0,
                'thoi_gian_ngoi': thoi_gian_ngoi
            })
            
        return JsonResponse({'status': 'success', 'data': list(zones_dict.values())})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required(login_url='login')
def api_mark_printing(request):
    """ API Đổi trạng thái bàn thành Chờ Thanh Toán khi Thu ngân In Bill """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hd_id = data.get('hoa_don_id')
            hd = HoaDon.objects.get(id=hd_id)
            
            if hd.ban_an:
                ban = hd.ban_an
                ban.trang_thai = 'cho_thanh_toan'
                ban.save()
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
@login_required(login_url='login')
def api_get_order(request, ban_id):
    """ API lấy chi tiết bill khi click vào bàn (ĐÃ FIX LỆCH MÚI GIỜ VÀ ĐỒNG BỘ PHÚT) """
    try:
        ban = get_object_or_404(BanAn, id=ban_id)
        hoa_don = HoaDon.objects.filter(ban_an=ban, trang_thai='dang_phuc_vu').first()
        
        if not hoa_don:
            return JsonResponse({'status': 'empty', 'ten_ban': ban.ten_ban, 'trang_thai': ban.trang_thai})
        
        # 1. Ép múi giờ UTC về giờ Việt Nam (Local Time)
        local_time = hoa_don.thoi_gian_vao

        if local_time and timezone.is_naive(local_time):
            local_time = timezone.make_aware(local_time)

        if local_time:
            local_time = timezone.localtime(local_time)
        
        # 2. Tính số phút khách đã ngồi (Giống hệt ở ngoài sơ đồ bàn)
        thoi_gian_ngoi = 0
        if hoa_don.thoi_gian_vao:
            time_diff = timezone.now() - hoa_don.thoi_gian_vao
            thoi_gian_ngoi = int(time_diff.total_seconds() / 60)
        
        items = [{
            'id': ct.id,
            'ten_mon': ct.ten_mon_luu_tru,
            'don_gia': float(ct.don_gia_luu_tru),
            'so_luong': ct.so_luong,
            'thanh_tien': float(ct.thanh_tien),
            'ghi_chu': getattr(ct, 'ghi_chu', '') 
        } for ct in hoa_don.chi_tiet.all()]
            
        return JsonResponse({
            'status': 'success',
            'ten_ban': ban.ten_ban,
            'trang_thai_ban': ban.trang_thai,
            'hoa_don_id': hoa_don.id,
            'ma_hoa_don': hoa_don.ma_hoa_don,
            'ma_voucher': hoa_don.ma_voucher or "",
            # Bổ sung an toàn or 0 tránh lỗi sập hệ thống khi biến bằng None
            'tien_giam_voucher': float(hoa_don.tien_giam_voucher or 0), 
            'timestamp_vao': local_time.isoformat() if local_time else "",
            'thoi_gian_vao': local_time.strftime("%H:%M") if local_time else "",
            'thoi_gian_ngoi': thoi_gian_ngoi,
            'tong_tien_hang': float(hoa_don.tong_tien_hang),
            'chiet_khau': float(hoa_don.chiet_khau), # Tổng khấu trừ (VIP + Voucher)
            'vat_phu_thu': float(hoa_don.vat_phu_thu),
            'tong_tien': float(hoa_don.khach_can_tra),
            'items': items
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': "Lỗi tải thông tin bàn: " + str(e)
        }, status=400)

@login_required(login_url='login')
def api_update_item(request):
    """ API Thêm món mới hoặc Tăng/giảm số lượng (CÓ TÍNH NĂNG CHỐNG GIAN LẬN) """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ban_id = data.get('ban_id')
            item_type = data.get('item_type') 
            item_id = data.get('item_id') 
            qty_change = int(data.get('qty_change', 1))

            try:
                setting = SystemSetting.objects.get(id=1)
                vat_rate = float(setting.vat_tax) if setting.vat_tax else 0.0
            except:
                vat_rate = 8.0 

            with transaction.atomic():
                # 1. TÌM BÀN VÀ HÓA ĐƠN TRƯỚC
                if item_type == 'update_only':
                    ct_hd = get_object_or_404(ChiTietHoaDon, id=item_id)
                    hoa_don = ct_hd.hoa_don
                    ban = hoa_don.ban_an
                else:
                    ban = get_object_or_404(BanAn, id=ban_id)
                    hoa_don, created = HoaDon.objects.get_or_create(
                        ban_an=ban, trang_thai='dang_phuc_vu',
                        defaults={'nhan_vien': request.user}
                    )

                # ==============================================================
                # 🔥 CHỐNG GIAN LẬN: KHÓA THÊM/XÓA MÓN KHI BÀN ĐANG CHỜ THANH TOÁN
                # ==============================================================
                if ban and ban.trang_thai == 'cho_thanh_toan':
                    return JsonResponse({
                        'status': 'error', 
                        'message': 'Bàn đã in Phiếu Tạm Tính 🖨️. Khóa chức năng sửa món để chống thất thoát! Vui lòng Hủy hóa đơn (Mục 3 chấm) nếu muốn đặt lại.'
                    }, status=400)

                # 2. TIẾP TỤC LOGIC CỘNG TRỪ MÓN (GIỮ NGUYÊN)
                if item_type == 'update_only':
                    ct_hd.so_luong += qty_change
                    if ct_hd.so_luong <= 0:
                        ct_hd.delete()
                    else:
                        ct_hd.thanh_tien = ct_hd.so_luong * ct_hd.don_gia_luu_tru
                        ct_hd.save()
                else:
                    # Ép bàn về trạng thái đang ăn khi có món mới
                    if ban.trang_thai == 'trong':
                        ban.trang_thai = 'dang_an'
                        ban.save()

                    if item_type == 'buffet':
                        mon = get_object_or_404(GoiBuffet, id=item_id)
                        ct_hd = ChiTietHoaDon.objects.filter(hoa_don=hoa_don, goi_buffet=mon).first()
                        ten_mon, don_gia = mon.ten_goi, mon.gia_ban 
                    elif item_type == 'drink':
                        mon = get_object_or_404(DoUongDichVu, id=item_id)
                        ct_hd = ChiTietHoaDon.objects.filter(hoa_don=hoa_don, do_uong=mon).first()
                        ten_mon, don_gia = mon.ten_mon, mon.gia_ban
                    else:
                        return JsonResponse({'status': 'error', 'message': 'Loại món không hợp lệ'}, status=400)

                    if ct_hd:
                        ct_hd.so_luong += qty_change
                        ct_hd.thanh_tien = ct_hd.so_luong * ct_hd.don_gia_luu_tru
                        ct_hd.save()
                    else:
                        ChiTietHoaDon.objects.create(
                            hoa_don=hoa_don, 
                            goi_buffet=mon if item_type == 'buffet' else None, 
                            do_uong=mon if item_type == 'drink' else None, 
                            ten_mon_luu_tru=ten_mon, 
                            don_gia_luu_tru=don_gia, 
                            so_luong=qty_change,
                            thanh_tien=don_gia * qty_change
                        )

                # 3. TÍNH LẠI VAT VÀ TỔNG TIỀN
                tong = sum(item.thanh_tien for item in hoa_don.chi_tiet.all())
                tong_float = float(tong)
                chiet_khau_float = float(hoa_don.chiet_khau)
                tien_vat = (tong_float - chiet_khau_float) * (vat_rate / 100.0)

                hoa_don.tong_tien_hang = tong
                hoa_don.vat_phu_thu = tien_vat
                hoa_don.khach_can_tra = tong_float + tien_vat - chiet_khau_float
                hoa_don.save()

            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
@login_required(login_url='login')
def api_checkout(request):
    """ API Thanh toán & Hủy hóa đơn (ĐÃ TÍCH HỢP CỘNG ĐIỂM VIP TỰ ĐỘNG) """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hd_id = data.get('hoa_don_id')
            method = data.get('phuong_thuc', 'tien_mat')
            action = data.get('action') 
            
            hoa_don = get_object_or_404(HoaDon, id=hd_id)
            
            with transaction.atomic():
                if action == 'cancel':
                    hoa_don.trang_thai = 'da_huy'
                    hoa_don.save()
                else:
                    ThanhToan.objects.create(
                        hoa_don=hoa_don, phuong_thuc=method,
                        so_tien_thu=hoa_don.khach_can_tra, nhan_vien_thu=request.user
                    )
                    hoa_don.trang_thai = 'da_thanh_toan'
                    hoa_don.thoi_gian_ra = timezone.now()
                    hoa_don.save()
                    
                    # ========================================================
                    # TỰ ĐỘNG CỘNG ĐIỂM KHI THANH TOÁN THÀNH CÔNG
                    # (Tỉ lệ: 10.000đ = 1 điểm)
                    # ========================================================
                    if hoa_don.khach_hang:
                        diem_cong_them = int(hoa_don.khach_can_tra / 10000)
                        kh = hoa_don.khach_hang
                        kh.diem_tich_luy += diem_cong_them
                        kh.save()
                
                if hoa_don.ban_an:
                    ban = hoa_don.ban_an
                    ban.trang_thai = 'trong'
                    ban.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
@login_required(login_url='login')
def api_unlock_table(request):
    """ API Mở khóa bàn khi lỡ in bill hoặc khách muốn gọi thêm món """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hd = HoaDon.objects.get(id=data.get('hoa_don_id'))
            if hd.ban_an:
                ban = hd.ban_an
                ban.trang_thai = 'dang_an' # Trả lại trạng thái Đang phục vụ
                ban.save()
                
                # Ghi Log bảo mật (Để quản lý biết ai đã mở khóa bill này)
                from core.models import SystemLog
                SystemLog.objects.create(
                    user=request.user, 
                    action=f"Mở khóa order Bàn {ban.ten_ban} (Mã HĐ: {hd.ma_hoa_don})", 
                    module="POS Bán hàng", 
                    level="warning"
                )
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
def print_bill_view(request, bill_id):
    hd = get_object_or_404(HoaDon, id=bill_id)
    
    # Kiểm tra xem có phải là lệnh in phiếu Bar/Bếp không
    # Nếu URL có dạng /print-bill/286/?type=bar thì biến is_bar = True
    is_bar = request.GET.get('type') == 'bar'
    
    # Tính toán tiền giảm giá để hiển thị
    tien_giam_voucher = float(hd.tien_giam_voucher or 0)
    tien_giam_vip = float(hd.chiet_khau or 0) - tien_giam_voucher
    
    context = {
        'hd': hd,
        'items': hd.chi_tiet.all(),
        'setting': SystemSetting.objects.get(id=1) if SystemSetting.objects.filter(id=1).exists() else None,
        'tien_giam_vip': tien_giam_vip,
        'tien_giam_voucher': tien_giam_voucher,
        'now': timezone.now(),
        'is_bar_ticket': is_bar  # Biến này quyết định ẩn/hiện tiền
    }
    return render(request, 'pos/print_bill.html', context)

# THÊM HÀM NÀY VÀO CUỐI FILE VIEWS.PY CỦA APP POS
@login_required
@require_POST
def api_update_note(request):
    try:
        data = json.loads(request.body)
        ct_id = data.get('ct_id')
        ghi_chu = data.get('ghi_chu', '')
        
        # LƯU Ý: Đổi 'ChiTietHoaDon' thành đúng tên Model chi tiết hóa đơn/order của bạn
        from .models import ChiTietHoaDon 
        
        chitiet = ChiTietHoaDon.objects.get(id=ct_id)
        chitiet.ghi_chu = ghi_chu
        chitiet.save()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
@login_required(login_url='login')
@require_POST
def api_apply_vip(request):
    """ API Kiểm tra SĐT khách hàng -> Gắn vào bill và Tự động áp dụng chiết khấu VIP """
    try:
        data = json.loads(request.body)
        hd_id = data.get('hoa_don_id')
        phone = (data.get('phone') or '').strip()

        hoa_don = get_object_or_404(HoaDon, id=hd_id)
        khach = KhachHang.objects.filter(so_dien_thoai=phone).first()

        if not khach:
            return JsonResponse({'status': 'error', 'message': 'Không tìm thấy khách hàng với Số điện thoại này!'})

        # Bọc AI trong try-except để nếu AI sập thì khách vẫn được giảm giá VIP
        voucher_data = []
        try:
            voucher_goi_y = ai_goi_y_voucher(khach, hoa_don.khach_can_tra)
            voucher_data = [{'ma_code': v.ma_code, 'muc_giam': v.muc_giam} for v in voucher_goi_y]
        except Exception as ai_error:
            print("Lỗi AI gợi ý:", str(ai_error)) # Bỏ qua lỗi AI, cho chạy tiếp

        # Xác định hạng thẻ và % giảm giá an toàn
        discount_percent = 0
        hang_the_str = "Thành viên"
        if khach.diem_tich_luy >= 1500:
            discount_percent = 10
            hang_the_str = "Kim Cương"
        elif khach.diem_tich_luy >= 500:
            discount_percent = 5
            hang_the_str = "Vàng"

        with transaction.atomic():
            # 1. Gắn khách hàng vào hóa đơn
            hoa_don.khach_hang = khach
            
            # 2. Tính tiền giảm VIP
            tong_float = float(hoa_don.tong_tien_hang or 0)
            tien_giam_vip = tong_float * (discount_percent / 100.0)
            
            # 3. Lấy lại tiền giảm Voucher cũ (nếu khách đã áp voucher trước đó)
            tien_giam_voucher = float(hoa_don.tien_giam_voucher or 0)

            # Tổng chiết khấu = VIP + Voucher (Không cho phép vượt quá tổng tiền hàng)
            tong_chiet_khau = tien_giam_vip + tien_giam_voucher
            if tong_chiet_khau > tong_float:
                tong_chiet_khau = tong_float

            hoa_don.chiet_khau = tong_chiet_khau

            # 4. Tính lại VAT và Khách cần trả
            try:
                setting = SystemSetting.objects.get(id=1)
                vat_rate = float(setting.vat_tax or 0)
            except:
                vat_rate = 8.0

            tien_vat = (tong_float - tong_chiet_khau) * (vat_rate / 100.0)
            hoa_don.vat_phu_thu = tien_vat
            hoa_don.khach_can_tra = tong_float + tien_vat - tong_chiet_khau
            hoa_don.save()

        msg = f'Đã áp dụng giảm {discount_percent}% cho khách {hang_the_str}' if discount_percent > 0 else 'Thành viên chưa đủ điểm giảm giá, nhưng vẫn được Tích điểm!'
        
        return JsonResponse({
            'status': 'success',
            'ho_ten': khach.ho_ten,
            'hang_the': hang_the_str,
            'chiet_khau': float(hoa_don.chiet_khau),
            'tong_tien': float(hoa_don.khach_can_tra),
            'voucher_goi_y': voucher_data,
            'message': msg
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': "Lỗi hệ thống: " + str(e)}, status=400)


@login_required(login_url='login')
@require_POST
def api_apply_voucher(request):
    """ API kiểm tra và áp dụng Voucher (cộng dồn với VIP, CHỈ CHO PHÉP 1 MÃ) """
    try:
        data = json.loads(request.body)
        hd_id = data.get('hoa_don_id')
        ma_code = (data.get('ma_code') or '').strip().upper()

        if not hd_id or not ma_code:
            return JsonResponse({'status': 'error', 'message': 'Dữ liệu không hợp lệ!'}, status=400)

        hoa_don = get_object_or_404(HoaDon, id=hd_id)

        # CHẶN NGAY NẾU ĐÃ CÓ MÃ VOUCHER
        if hoa_don.ma_voucher:
            if hoa_don.ma_voucher.upper() == ma_code:
                return JsonResponse({'status': 'error', 'message': 'Mã voucher này đã được áp dụng cho hóa đơn!'})
            else:
                return JsonResponse({'status': 'error', 'message': f'Hóa đơn đã áp dụng mã {hoa_don.ma_voucher}. Chỉ được dùng 1 mã!'})

        from customers.models import Voucher
        voucher = Voucher.objects.filter(ma_code__iexact=ma_code).first()

        if not voucher:
            return JsonResponse({'status': 'error', 'message': 'Mã khuyến mãi không tồn tại!'})
        if getattr(voucher, 'trang_thai', True) == False: # Đề phòng trường hợp field boolean là False
            return JsonResponse({'status': 'error', 'message': 'Voucher đã bị khóa!'})
        if getattr(voucher, 'da_het_han', False) == True:
            return JsonResponse({'status': 'error', 'message': 'Voucher đã hết hạn!'})

        tong_tien_hang = float(hoa_don.tong_tien_hang or 0)
        if tong_tien_hang < float(voucher.dieu_kien_toi_thieu or 0):
            return JsonResponse({'status': 'error', 'message': f'Bill chưa đạt tối thiểu {voucher.dieu_kien_toi_thieu:,.0f}đ!'})

        with transaction.atomic():
            # 1. TÍNH TIỀN GIẢM VOUCHER
            tien_giam_voucher = 0
            muc_giam_str = str(voucher.muc_giam).replace(' ', '')
            
            if '%' in muc_giam_str:
                pt_giam = float(muc_giam_str.replace('%', ''))
                tien_giam_voucher = tong_tien_hang * (pt_giam / 100.0)
            else:
                tien_giam_voucher = float(muc_giam_str.replace(',', '').replace('.', '').replace('đ', ''))

            # 2. TÍNH LẠI TỔNG CHIẾT KHẤU (Giữ lại phần giảm VIP cũ)
            # Tiền VIP = Tổng chiết khấu cũ - Tiền voucher cũ (mà voucher cũ = 0 vì đã check ở trên)
            tien_giam_vip = float(hoa_don.chiet_khau or 0) - float(hoa_don.tien_giam_voucher or 0)
            
            tong_giam_gia = tien_giam_vip + tien_giam_voucher
            if tong_giam_gia > tong_tien_hang:
                tong_giam_gia = tong_tien_hang

            # 3. TÍNH LẠI VAT
            try:
                setting = SystemSetting.objects.get(id=1)
                vat_rate = float(setting.vat_tax or 0)
            except:
                vat_rate = 8.0

            tien_vat = (tong_tien_hang - tong_giam_gia) * (vat_rate / 100.0)

            # 4. CẬP NHẬT HÓA ĐƠN
            hoa_don.chiet_khau = tong_giam_gia
            hoa_don.ma_voucher = voucher.ma_code
            hoa_don.tien_giam_voucher = tien_giam_voucher
            hoa_don.vat_phu_thu = tien_vat
            hoa_don.khach_can_tra = tong_tien_hang + tien_vat - tong_giam_gia

            # Ghi chú hóa đơn
            old_note = hoa_don.ghi_chu or ""
            voucher_note = f"[Voucher: {voucher.ma_code}]"
            if voucher_note not in old_note:
                hoa_don.ghi_chu = f"{old_note} {voucher_note}".strip()

            hoa_don.save()

        return JsonResponse({
            'status': 'success',
            'voucher': {'ma_code': voucher.ma_code, 'muc_giam': voucher.muc_giam},
            'tien_giam_voucher': float(tien_giam_voucher),
            'tong_chiet_khau': float(hoa_don.chiet_khau),
            'tong_tien': float(hoa_don.khach_can_tra),
            'message': f'Áp dụng voucher {voucher.ma_code} thành công!'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': "Lỗi hệ thống: " + str(e)}, status=400)

@login_required(login_url='login')
@require_POST
def api_remove_voucher(request):
    """ API gỡ mã voucher khỏi hóa đơn """
    try:
        data = json.loads(request.body)
        hd_id = data.get('hoa_don_id')
        hoa_don = get_object_or_404(HoaDon, id=hd_id)

        if not hoa_don.ma_voucher:
            return JsonResponse({'status': 'error', 'message': 'Hóa đơn chưa áp dụng voucher nào!'})

        with transaction.atomic():
            # 1. Bóc tách tiền: Tổng chiết khấu mới = Tổng chiết khấu cũ - Tiền voucher
            tien_giam_voucher = float(hoa_don.tien_giam_voucher or 0)
            tien_giam_vip = float(hoa_don.chiet_khau or 0) - tien_giam_voucher
            
            # Reset voucher về số 0
            hoa_don.chiet_khau = tien_giam_vip
            hoa_don.ma_voucher = None
            hoa_don.tien_giam_voucher = 0

            # 2. Tính lại VAT và số tiền Khách cần trả
            tong_tien_hang = float(hoa_don.tong_tien_hang or 0)
            try:
                from core.models import SystemSetting
                setting = SystemSetting.objects.get(id=1)
                vat_rate = float(setting.vat_tax or 0)
            except:
                vat_rate = 8.0

            tien_vat = (tong_tien_hang - tien_giam_vip) * (vat_rate / 100.0)
            hoa_don.vat_phu_thu = tien_vat
            hoa_don.khach_can_tra = tong_tien_hang + tien_vat - tien_giam_vip

            # Xóa chữ "[Voucher: ...]" trong ghi chú (nếu có)
            import re
            if hoa_don.ghi_chu:
                hoa_don.ghi_chu = re.sub(r'\[Voucher:.*?\]', '', hoa_don.ghi_chu).strip()

            hoa_don.save()

        return JsonResponse({
            'status': 'success',
            'tong_tien': float(hoa_don.khach_can_tra),
            'message': 'Đã hủy mã Voucher thành công!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)