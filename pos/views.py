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
from .models import HoaDon, ChiTietHoaDon
from menu.models import ThucDon
from reception.models import BanAn, PhieuDatBan, KhuVuc
from customers.models import KhachHang
from core.models import SystemSetting 

# ==========================================
# 1. MÀN HÌNH BÁN HÀNG (POS THU NGÂN SPA)
# ==========================================
@login_required(login_url='login')
def pos_view(request):
    try:
        goi_buffet = ThucDon.objects.filter(loai_mon='goi_buffet', trang_thai=True)
        do_uong = ThucDon.objects.filter(loai_mon='do_uong', trang_thai=True)
        dich_vu = ThucDon.objects.filter(loai_mon='dich_vu', trang_thai=True)
    except:
        goi_buffet = ThucDon.objects.filter(loai_mon='goi_buffet')
        do_uong = ThucDon.objects.filter(loai_mon='do_uong')
        dich_vu = ThucDon.objects.filter(loai_mon='dich_vu')

    # KIỂM TRA PHÂN QUYỀN VÀ CHỨC VỤ
    is_cashier = False
    user_roles = []

    if request.user.is_superuser:
        is_cashier = True
        user_roles.append("Administrator")
    
    for group in request.user.groups.all():
        user_roles.append(group.name)
        if hasattr(group, 'quyen') and group.quyen.pos_checkout:
            is_cashier = True

    user_role_name = " / ".join(user_roles) if user_roles else "Nhân viên"

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
        'dich_vu': dich_vu,
        'is_cashier': is_cashier,
        'user_role_name': user_role_name,
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
            
            hd.phuong_thuc_tt = method
            hd.so_tien_thu = hd.khach_can_tra
            hd.ngay_thanh_toan = timezone.now()
            
            hd.trang_thai = 'da_thanh_toan'
            hd.thoi_gian_ra = timezone.now()
            
            if hd.ban_an:
                hd.ban_an.trang_thai = 'trong'
                hd.ban_an.save()
                
            hd.save()
            messages.success(request, f"Đã thanh toán thành công {hd.ma_hoa_don}!")
            return redirect('/pos/payments/')

    # Nới lỏng giới hạn load 1500 hóa đơn gần nhất để filter JS có thể hoạt động hiệu quả với dữ liệu mẫu lớn
    danh_sach_hoa_don = HoaDon.objects.select_related('ban_an', 'khach_hang', 'nhan_vien').all().order_by('-id')[:1500]
    today = timezone.now().date()
    open_bills_count = HoaDon.objects.filter(trang_thai='dang_phuc_vu').count()
    pending_bills_count = HoaDon.objects.filter(trang_thai='cho_thanh_toan').count()
    paid_bills_count = HoaDon.objects.filter(trang_thai='da_thanh_toan', thoi_gian_vao__date=today).count()
    
    context = {
        'danh_sach_hoa_don': danh_sach_hoa_don,
        'open_bills_count': open_bills_count,
        'pending_bills_count': pending_bills_count,
        'paid_bills_count': paid_bills_count,
    }
    return render(request, 'pos/payments.html', context)


# ==========================================
# 3. LỊCH SỬ HÓA ĐƠN (INVOICE LIST)
# ==========================================
@login_required(login_url='login')
def invoice_list(request):
    from django.db.models import Count, Q
    from django.core.paginator import Paginator

    qs = HoaDon.objects.select_related('ban_an', 'khach_hang', 'nhan_vien').filter(trang_thai='da_thanh_toan').order_by('-id')

    # Xử lý Server-side Filtering
    search_query = request.GET.get('q', '').strip()
    method_filter = request.GET.get('method', 'all')
    date_filter = request.GET.get('date', '')

    if search_query:
        qs = qs.filter(ma_hoa_don__icontains=search_query)
    if method_filter != 'all':
        qs = qs.filter(phuong_thuc_tt=method_filter)
    if date_filter:
        qs = qs.filter(thoi_gian_ra__date=date_filter)
    # Tổng hợp bằng SQL thay vì Python loop
    agg = qs.aggregate(
        total_revenue=Sum('khach_can_tra'),
        total_card_bank=Sum('so_tien_thu', filter=~Q(phuong_thuc_tt='tien_mat') & ~Q(phuong_thuc_tt=None))
    )
    total_txns = qs.count()
    total_revenue = agg['total_revenue'] or 0
    total_card_bank = agg['total_card_bank'] or 0

    # Phân trang: mỗi trang 50 hóa đơn
    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'danh_sach_hoa_don': page_obj,
        'page_obj': page_obj,
        'total_txns': total_txns,
        'total_revenue': total_revenue,
        'total_card_bank': total_card_bank,
        'search_query': search_query,
        'method_filter': method_filter,
        'date_filter': date_filter,
    }
    return render(request, 'pos/invoices.html', context)


# ==========================================
# 4. AJAX: LẤY CHI TIẾT HÓA ĐƠN Ở BẢNG QUẢN TRỊ
# ==========================================
@login_required(login_url='login')
def invoice_detail_ajax(request, pk):
    try:
        hd = get_object_or_404(HoaDon.objects.select_related('ban_an'), id=pk)
        items_data = [{
            'ten_mon': item.ten_mon_luu_tru or 'Món không tên',
            'so_luong': item.so_luong or 1,
            'don_gia': float(item.don_gia_luu_tru or 0),
            'thanh_tien': float(item.thanh_tien or 0)
        } for item in hd.chi_tiet.all()]

        return JsonResponse({
            'status': 'success',
            'ma_hoa_don': hd.ma_hoa_don,
            'ten_ban': hd.ban_an.ten_ban if hd.ban_an else 'Mang đi',
            'thoi_gian_vao': hd.thoi_gian_vao.strftime("%H:%M - %d/%m/%Y") if hd.thoi_gian_vao else '',
            'tong_tien_hang': float(hd.tong_tien_hang or 0),
            'chiet_khau': float(hd.chiet_khau or 0),
            'vat_phu_thu': float(hd.vat_phu_thu or 0),
            'khach_can_tra': float(hd.khach_can_tra or 0),
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

    for hd in HoaDon.objects.select_related('nhan_vien').filter(trang_thai='da_thanh_toan').order_by('-id'):
        phuong_thuc = hd.get_phuong_thuc_tt_display() if hd.phuong_thuc_tt else "Tiền mặt"
        ma_gd = f"TXN-{hd.id:04d}"
        thoi_gian = hd.thoi_gian_ra.strftime("%Y-%m-%d %H:%M") if hd.thoi_gian_ra else ""
        nhan_vien = hd.nhan_vien.username if hd.nhan_vien else "Hệ thống"
        writer.writerow([ma_gd, hd.ma_hoa_don, thoi_gian, phuong_thuc, hd.khach_can_tra, nhan_vien])

    return response


# =========================================================================
# PHẦN API DÀNH RIÊNG CHO GIAO DIỆN SPA CỦA BÁN HÀNG TẠI QUẦY (FRONTEND JS)
# =========================================================================

@login_required(login_url='login')
def api_load_tables(request):
    """ API Load sơ đồ bàn phân theo khu vực (Đã bổ sung Sắp xếp chuẩn, Ẩn bàn đã xóa và Trạng thái Chờ thanh toán) """
    try:
        danh_sach_ban = list(BanAn.objects.exclude(trang_thai='da_xoa'))
        
        def natural_sort_key(ban):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', ban.ten_ban)]
        danh_sach_ban.sort(key=natural_sort_key)

        khu_vuc_dict = {kv.id: kv.ten_khu_vuc for kv in KhuVuc.objects.all()}
        zones_dict = {}
        for ban in danh_sach_ban:
            kv_id = ban.khu_vuc_id if ban.khu_vuc_id else "Chung"
            kv_ten = khu_vuc_dict.get(ban.khu_vuc_id, "Khu vực chung")
            
            if kv_id not in zones_dict:
                zones_dict[kv_id] = {'khu_vuc_id': kv_id, 'ten_khu_vuc': kv_ten, 'ban_list': []}
                
            hd = HoaDon.objects.filter(ban_an=ban, trang_thai__in=['dang_phuc_vu', 'cho_thanh_toan']).first()
            
            # XÁC ĐỊNH TRẠNG THÁI BÀN
            if hd:
                if hd.trang_thai == 'cho_thanh_toan' or ban.trang_thai == 'cho_thanh_toan':
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
            
            # Lưu lại trạng thái hóa đơn để hiển thị trên màn hình Payments
            hd.trang_thai = 'cho_thanh_toan'
            hd.save()
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
@login_required(login_url='login')
def api_get_order(request, ban_id):
    """ API lấy chi tiết bill khi click vào bàn (ĐÃ FIX LỆCH MÚI GIỜ VÀ ĐỒNG BỘ PHÚT) """
    try:
        ban = get_object_or_404(BanAn, id=ban_id)
        hoa_don = HoaDon.objects.filter(ban_an=ban, trang_thai__in=['dang_phuc_vu', 'cho_thanh_toan']).first()
        
        if not hoa_don:
            return JsonResponse({'status': 'empty', 'ten_ban': ban.ten_ban, 'trang_thai': ban.trang_thai})
        
        # 1. Thời gian khách vào (Local Time do USE_TZ=False)
        local_time = hoa_don.thoi_gian_vao
        
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
        } for ct in hoa_don.chi_tiet.filter(so_luong__gt=0)]
            
        # Thêm AI gợi ý voucher nếu có khách hàng
        voucher_goi_y = []
        if hoa_don.khach_hang:
            try:
                vouchers_obj = ai_goi_y_voucher(hoa_don.khach_hang, float(hoa_don.tong_tien_hang))
                voucher_goi_y = [{
                    'ma_code': v.ma_code,
                    'muc_giam': v.muc_giam,
                    'gan_du': getattr(v, '_gan_du', False),
                    'so_tien_thieu': float(v.dieu_kien_toi_thieu) - float(hoa_don.tong_tien_hang) if getattr(v, '_gan_du', False) else 0
                } for v in vouchers_obj]
            except Exception:
                pass

        return JsonResponse({
            'status': 'success',
            'ten_ban': ban.ten_ban,
            'trang_thai_ban': 'cho_thanh_toan' if (hoa_don and hoa_don.trang_thai == 'cho_thanh_toan') else ban.trang_thai,
            'hoa_don_id': hoa_don.id,
            'ma_hoa_don': hoa_don.ma_hoa_don,
            'ma_voucher': hoa_don.ma_voucher or "",
            'tien_giam_voucher': 0, 
            'timestamp_vao': local_time.isoformat() if local_time else "",
            'thoi_gian_vao': local_time.strftime("%H:%M") if local_time else "",
            'thoi_gian_ngoi': thoi_gian_ngoi,
            'tong_tien_hang': float(hoa_don.tong_tien_hang),
            'chiet_khau': float(hoa_don.chiet_khau), # Tổng khấu trừ (VIP + Voucher)
            'vat_phu_thu': float(hoa_don.vat_phu_thu),
            'tong_tien': float(hoa_don.khach_can_tra),
            'khach_hang_phone': hoa_don.khach_hang.so_dien_thoai if hoa_don.khach_hang else None,
            'khach_hang_ho_ten': hoa_don.khach_hang.ho_ten if hoa_don.khach_hang else None,
            'khach_hang_hang_the': getattr(hoa_don.khach_hang, 'hang_the', 'Thành viên') if hoa_don.khach_hang else None,
            'voucher_goi_y': voucher_goi_y,
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
                sc_rate = float(setting.service_charge) if setting.service_charge else 0.0
            except:
                vat_rate = 8.0 
                sc_rate = 0.0 

            with transaction.atomic():
                if item_type == 'update_only':
                    ct_hd = get_object_or_404(ChiTietHoaDon, id=item_id)
                    hoa_don = ct_hd.hoa_don
                    ban = hoa_don.ban_an
                else:
                    ban = get_object_or_404(BanAn, id=ban_id)
                    # ✅ FIX: Tìm HoaDon đang mở (dang_phuc_vu HOẶC cho_thanh_toan)
                    hoa_don = (
                        HoaDon.objects
                        .select_for_update()  # Lock row để tránh race condition
                        .filter(ban_an=ban, trang_thai__in=['dang_phuc_vu', 'cho_thanh_toan'])
                        .first()
                    )

                # ==============================================================
                # 🔥 CHỐNG GIAN LẬN: KHÓA THÊM/XÓA MÓN KHI BÀN ĐANG CHỜ THANH TOÁN
                # ==============================================================
                if (hoa_don and hoa_don.trang_thai == 'cho_thanh_toan') or (ban and ban.trang_thai == 'cho_thanh_toan'):
                    return JsonResponse({
                        'status': 'error', 
                        'message': 'Bàn đã in Phiếu Tạm Tính 🖨️. Khóa chức năng sửa món để chống thất thoát! Vui lòng Hủy hóa đơn (Mục 3 chấm) nếu muốn đặt lại.'
                    }, status=400)
                
                if not hoa_don and item_type != 'update_only':
                    # Bàn chưa có HoaDon → tạo mới
                    hoa_don = HoaDon.objects.create(
                        ban_an=ban,
                        trang_thai='dang_phuc_vu',
                        nhan_vien=request.user,
                    )

                # 2. TIẾP TỤC LOGIC CỘNG TRỪ MÓN
                if item_type == 'update_only':
                    new_qty = ct_hd.so_luong + qty_change
                    if new_qty < ct_hd.so_luong_da_in:
                        return JsonResponse({
                            'status': 'error', 
                            'message': f'Không thể giảm dưới số lượng đã in bếp ({ct_hd.so_luong_da_in}). Vui lòng báo quản lý nếu khách thực sự muốn hủy món đã làm.'
                        }, status=400)
                        
                    ct_hd.so_luong = new_qty
                    if ct_hd.so_luong <= 0:
                        ct_hd.delete()
                    else:
                        ct_hd.thanh_tien = ct_hd.so_luong * ct_hd.don_gia_luu_tru
                        ct_hd.save()
                else:
                    # Ép bàn về trạng thái đang ăn khi có món mới
                    if ban.trang_thai in ['trong', 'da_dat']:
                        ban.trang_thai = 'dang_an'
                        ban.save()

                    mon = get_object_or_404(ThucDon, id=item_id)
                    ct_hd = ChiTietHoaDon.objects.filter(hoa_don=hoa_don, thuc_don=mon, don_gia_luu_tru=mon.gia_ban).first()
                    ten_mon, don_gia = mon.ten_mon, mon.gia_ban

                    if ct_hd:
                        ct_hd.so_luong += qty_change
                        ct_hd.thanh_tien = ct_hd.so_luong * ct_hd.don_gia_luu_tru
                        ct_hd.save()
                    else:
                        ChiTietHoaDon.objects.create(
                            hoa_don=hoa_don, 
                            thuc_don=mon,
                            ten_mon_luu_tru=ten_mon, 
                            don_gia_luu_tru=don_gia, 
                            so_luong=qty_change,
                            thanh_tien=don_gia * qty_change
                        )

                # 3. KIỂM TRA LẠI ĐIỀU KIỆN VOUCHER NẾU CÓ
                tong = sum(item.thanh_tien for item in hoa_don.chi_tiet.all())
                tong_float = float(tong)
                
                if hoa_don.ma_voucher:
                    from customers.models import Voucher
                    voucher = Voucher.objects.filter(ma_code__iexact=hoa_don.ma_voucher).first()
                    if voucher and tong_float < float(voucher.dieu_kien_toi_thieu):
                        # Gỡ voucher vì không đủ điều kiện
                        hoa_don.ma_voucher = None
                        hoa_don.chiet_khau = 0 # Hoặc tính lại chiết khấu VIP nếu có (đơn giản hóa thì reset = 0)
                        
                        # Xóa text ghi chú voucher
                        if hoa_don.ghi_chu:
                            hoa_don.ghi_chu = hoa_don.ghi_chu.replace(f"[Voucher: {voucher.ma_code}]", "").strip()

                chiet_khau_float = float(hoa_don.chiet_khau)
                tien_sc = (tong_float - chiet_khau_float) * (sc_rate / 100.0)
                tien_vat = (tong_float - chiet_khau_float + tien_sc) * (vat_rate / 100.0)

                # 4. CẬP NHẬT LẠI SỐ KHÁCH DỰA VÀO TỔNG SỐ VÉ BUFFET
                tong_khach = 0
                for item in hoa_don.chi_tiet.all():
                    if item.thuc_don and item.thuc_don.loai_mon == 'goi_buffet':
                        tong_khach += item.so_luong
                    elif 'vé' in item.ten_mon_luu_tru.lower() or 'buffet' in item.ten_mon_luu_tru.lower():
                        tong_khach += item.so_luong
                        
                hoa_don.so_khach = tong_khach if tong_khach > 0 else 1

                hoa_don.tong_tien_hang = tong
                hoa_don.vat_phu_thu = tien_vat + tien_sc
                hoa_don.khach_can_tra = tong_float - chiet_khau_float + tien_sc + tien_vat
                hoa_don.save()

            return JsonResponse({'status': 'success'})
        except Exception as e:
            import traceback
            traceback.print_exc()  # In lỗi chi tiết ra terminal để debug
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
            
            # KIỂM TRA PHÂN QUYỀN BACKEND (Chống hack API)
            has_checkout_perm = False
            if request.user.is_superuser:
                has_checkout_perm = True
            else:
                for group in request.user.groups.all():
                    if hasattr(group, 'quyen') and group.quyen.pos_checkout:
                        has_checkout_perm = True
                        break
            
            if not has_checkout_perm:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Lỗi Phân Quyền: Tài khoản của bạn không được cấp phép thực hiện Thanh toán/Hủy bàn!'
                }, status=403)

            with transaction.atomic():
                if action == 'cancel':
                    hoa_don.trang_thai = 'da_huy'
                    hoa_don.save()
                    if hoa_don.ban_an:
                        hoa_don.ban_an.trang_thai = 'trong'
                        hoa_don.ban_an.save()
                else:
                    hoa_don.phuong_thuc_tt = method
                    hoa_don.so_tien_thu = hoa_don.khach_can_tra
                    hoa_don.ngay_thanh_toan = timezone.now()
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

                    # ========================================================
                    # AUTO-INVENTORY DEDUCTION (TỰ ĐỘNG TRỪ KHO ĐỒ UỐNG)
                    # ========================================================
                    from inventory.models import NguyenLieu, PhieuKho, ChiTietPhieuKho
                    
                    # Tìm tất cả đồ uống trong hóa đơn
                    chi_tiet_do_uong = ChiTietHoaDon.objects.filter(
                        hoa_don=hoa_don, 
                        thuc_don__loai_mon='do_uong'
                    )
                    
                    if chi_tiet_do_uong.exists():
                        # Khởi tạo Phiếu xuất kho tự động
                        phieu_xuat = PhieuKho.objects.create(
                            loai_phieu='xuat',
                            nguoi_thuc_hien=request.user if request.user.is_authenticated else None,
                            ghi_chu=f"Tự động xuất bán từ POS - Hóa Đơn #{hoa_don.id}",
                            da_thanh_toan=True,
                            tong_tien=0
                        )
                        tong_tien_xuat = 0
                        
                        danh_sach_nl = list(NguyenLieu.objects.all())
                        
                        for ct in chi_tiet_do_uong:
                            ten_mon = ct.thuc_don.ten_mon.lower()
                            # Tìm nguyên liệu có tên gần giống món nhất
                            nl_match = None
                            for nl in danh_sach_nl:
                                ten_nl = nl.ten_nguyen_lieu.lower()
                                # Chặn các từ quá ngắn như 'nước', 'bia' gây match nhầm
                                if len(ten_nl) > 3 and (ten_nl in ten_mon or ten_mon in ten_nl):
                                    nl_match = nl
                                    break
                            
                            if nl_match:
                                # Trừ tồn kho
                                so_luong_tru = ct.so_luong
                                nl_match.ton_kho -= so_luong_tru
                                nl_match.save()
                                
                                # Lưu chi tiết phiếu xuất
                                don_gia_xuat = nl_match.don_gia_trung_binh or 0
                                thanh_tien_xuat = so_luong_tru * don_gia_xuat
                                tong_tien_xuat += thanh_tien_xuat
                                
                                ChiTietPhieuKho.objects.create(
                                    phieu=phieu_xuat,
                                    nguyen_lieu=nl_match,
                                    so_luong=so_luong_tru,
                                    don_gia=don_gia_xuat,
                                    thanh_tien=thanh_tien_xuat,
                                    ghi_chu=f"Xuất bán món: {ct.thuc_don.ten_mon}"
                                )
                        
                        # Cập nhật tổng tiền phiếu xuất
                        phieu_xuat.tong_tien = tong_tien_xuat
                        phieu_xuat.save()
                        
                        # Xóa phiếu xuất nếu không có nguyên liệu nào match (tránh rác DB)
                        if phieu_xuat.chi_tiet.count() == 0:
                            phieu_xuat.delete()
                
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

            # Đổi trạng thái hóa đơn về dang_phuc_vu để mở khóa sửa món
            if hd.trang_thai == 'cho_thanh_toan':
                hd.trang_thai = 'dang_phuc_vu'
                hd.save()

            if hd.ban_an:
                ban = hd.ban_an
                ban.trang_thai = 'dang_an'  # Trả lại trạng thái Đang phục vụ
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
    tien_giam_voucher = 0
    tien_giam_vip = float(hd.chiet_khau or 0)
    
    items_to_print = []
    
    has_printed_before = sum(item.so_luong_da_in for item in hd.chi_tiet.all()) > 0
    has_return = any(item.so_luong < item.so_luong_da_in for item in hd.chi_tiet.all())
    
    if has_return:
        ticket_title = "PHIẾU TRẢ ĐỒ / BỔ SUNG"
        ticket_title_cashier = "PHIẾU TRẢ VÉ / BỔ SUNG"
    else:
        ticket_title = "PHIẾU ĐỒ BỔ SUNG" if has_printed_before else "PHIẾU CHẾ BIẾN (QUẦY BAR)"
        ticket_title_cashier = "PHIẾU BỔ SUNG VÉ" if has_printed_before else "PHIẾU KIỂM SOÁT (THU NGÂN)"
    
    bar_items = []
    cashier_items = []
    
    if is_bar:
        # In phiếu Bar/Bếp: Chỉ in các món có thay đổi (Bổ sung hoặc Trả món)
        for item in hd.chi_tiet.all():
            delta = item.so_luong - item.so_luong_da_in
            if delta != 0:
                item.in_so_luong = abs(delta)
                item.in_loai = "TRẢ MÓN" if delta < 0 else ""
                items_to_print.append(item)
                
                ten_mon_lower = item.ten_mon_luu_tru.lower()
                if "vé" in ten_mon_lower or "buffet" in ten_mon_lower or "phụ thu" in ten_mon_lower or "phí" in ten_mon_lower:
                    cashier_items.append(item)
                else:
                    bar_items.append(item)
                
                # Cập nhật số lượng đã in vào database
                item.so_luong_da_in = item.so_luong
                item.save(update_fields=['so_luong_da_in'])
                
                # Nếu món đã bị trả hết và in xong phiếu trả thì xóa hẳn
                if item.so_luong == 0 and item.so_luong_da_in == 0:
                    item.delete()
    else:
        # In phiếu Tạm tính: In toàn bộ món
        for item in hd.chi_tiet.filter(so_luong__gt=0):
            item.in_so_luong = item.so_luong
            items_to_print.append(item)
    
    context = {
        'hd': hd,
        'items': items_to_print,
        'bar_items': bar_items,
        'cashier_items': cashier_items,
        'setting': SystemSetting.objects.get(id=1) if SystemSetting.objects.filter(id=1).exists() else None,
        'tien_giam_vip': tien_giam_vip,
        'tien_giam_voucher': tien_giam_voucher,
        'now': timezone.now(),
        'is_bar_ticket': is_bar,
        'ticket_title': ticket_title,
        'ticket_title_cashier': ticket_title_cashier
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
            voucher_data = [
                {
                    'ma_code': v.ma_code,
                    'muc_giam': v.muc_giam,
                    'dieu_kien': float(v.dieu_kien_toi_thieu or 0),
                    'gan_du': getattr(v, '_gan_du', False),
                }
                for v in voucher_goi_y
            ]
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
            tien_giam_voucher = 0

            # Tổng chiết khấu = VIP + Voucher (Không cho phép vượt quá tổng tiền hàng)
            tong_chiet_khau = tien_giam_vip + tien_giam_voucher
            if tong_chiet_khau > tong_float:
                tong_chiet_khau = tong_float

            hoa_don.chiet_khau = tong_chiet_khau

            # 4. Tính lại SC, VAT và Khách cần trả
            try:
                setting = SystemSetting.objects.get(id=1)
                vat_rate = float(setting.vat_tax or 0)
                sc_rate = float(setting.service_charge or 0)
            except:
                vat_rate = 8.0
                sc_rate = 0.0

            tien_sc = (tong_float - tong_chiet_khau) * (sc_rate / 100.0)
            tien_vat = (tong_float - tong_chiet_khau + tien_sc) * (vat_rate / 100.0)
            
            hoa_don.vat_phu_thu = tien_vat + tien_sc
            hoa_don.khach_can_tra = tong_float - tong_chiet_khau + tien_sc + tien_vat
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
def api_remove_vip(request):
    """ API Hủy áp dụng Khách hàng VIP """
    try:
        data = json.loads(request.body)
        hd_id = data.get('hoa_don_id')
        hoa_don = get_object_or_404(HoaDon, id=hd_id)

        with transaction.atomic():
            hoa_don.khach_hang = None
            
            # Giữ lại tiền voucher nếu có
            tong_float = float(hoa_don.tong_tien_hang or 0)
            
            # Nếu có voucher, ta vẫn giữ voucher, tính lại chiết khấu chỉ bằng voucher (nếu cần thiết phải xử lý voucher, ở đây ta có thể xóa luon voucher cho an toàn hoặc chỉ bỏ phần VIP).
            # Do hệ thống lưu chung 'chiet_khau' nên ta sẽ reset chiet_khau. 
            # Giả sử voucher bị reset khi hủy KH để tránh lỗi logic, nếu khách muốn áp voucher phải nhập lại.
            hoa_don.ma_voucher = None
            hoa_don.chiet_khau = 0
            if hoa_don.ghi_chu and '[Voucher:' in hoa_don.ghi_chu:
                import re
                hoa_don.ghi_chu = re.sub(r'\[Voucher:[^\]]+\]', '', hoa_don.ghi_chu).strip()

            try:
                setting = SystemSetting.objects.get(id=1)
                vat_rate = float(setting.vat_tax or 0)
                sc_rate = float(setting.service_charge or 0)
            except:
                vat_rate = 8.0
                sc_rate = 0.0

            tien_sc = (tong_float - 0) * (sc_rate / 100.0)
            tien_vat = (tong_float - 0 + tien_sc) * (vat_rate / 100.0)
            
            hoa_don.vat_phu_thu = tien_vat + tien_sc
            hoa_don.khach_can_tra = tong_float + tien_sc + tien_vat
            hoa_don.save()

        return JsonResponse({
            'status': 'success',
            'tong_tien': float(hoa_don.khach_can_tra),
            'message': 'Đã hủy thành viên thành công. Vui lòng áp dụng lại voucher nếu cần.'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': "Lỗi hệ thống: " + str(e)}, status=400)

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
            tien_giam_vip = float(hoa_don.chiet_khau or 0)
            
            tong_giam_gia = tien_giam_vip + tien_giam_voucher
            if tong_giam_gia > tong_tien_hang:
                tong_giam_gia = tong_tien_hang

            # 3. TÍNH LẠI SC, VAT
            try:
                setting = SystemSetting.objects.get(id=1)
                vat_rate = float(setting.vat_tax or 0)
                sc_rate = float(setting.service_charge or 0)
            except:
                vat_rate = 8.0
                sc_rate = 0.0

            tien_sc = (tong_tien_hang - tong_giam_gia) * (sc_rate / 100.0)
            tien_vat = (tong_tien_hang - tong_giam_gia + tien_sc) * (vat_rate / 100.0)

            hoa_don.chiet_khau = tong_giam_gia
            hoa_don.ma_voucher = voucher.ma_code
            hoa_don.vat_phu_thu = tien_vat + tien_sc
            hoa_don.khach_can_tra = tong_tien_hang - tong_giam_gia + tien_sc + tien_vat

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
            tien_giam_voucher = 0
            if hoa_don.ma_voucher:
                from customers.models import Voucher
                voucher = Voucher.objects.filter(ma_code__iexact=hoa_don.ma_voucher).first()
                if voucher:
                    muc_giam_str = str(voucher.muc_giam).replace(' ', '')
                    if '%' in muc_giam_str:
                        tien_giam_voucher = float(hoa_don.tong_tien_hang or 0) * (float(muc_giam_str.replace('%', '')) / 100.0)
                    else:
                        tien_giam_voucher = float(muc_giam_str.replace(',', '').replace('.', '').replace('đ', ''))
                        
            tien_giam_vip = float(hoa_don.chiet_khau or 0) - tien_giam_voucher
            
            # Reset voucher về số 0
            hoa_don.chiet_khau = max(0, tien_giam_vip)
            hoa_don.ma_voucher = None

            # 2. Tính lại SC, VAT và số tiền Khách cần trả
            tong_tien_hang = float(hoa_don.tong_tien_hang or 0)
            try:
                from core.models import SystemSetting
                setting = SystemSetting.objects.get(id=1)
                vat_rate = float(setting.vat_tax or 0)
                sc_rate = float(setting.service_charge or 0)
            except:
                vat_rate = 8.0
                sc_rate = 0.0

            tien_sc = (tong_tien_hang - tien_giam_vip) * (sc_rate / 100.0)
            tien_vat = (tong_tien_hang - tien_giam_vip + tien_sc) * (vat_rate / 100.0)
            
            hoa_don.vat_phu_thu = tien_vat + tien_sc
            hoa_don.khach_can_tra = tong_tien_hang - tien_giam_vip + tien_sc + tien_vat

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