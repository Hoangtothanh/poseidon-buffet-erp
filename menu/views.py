from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ThucDon

# ==========================================
# 1. QUẢN LÝ GÓI BUFFET (Đã bổ sung Khung Giờ Bán)
# ==========================================
@login_required(login_url='login')
def buffet_packages_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        ve_id = request.POST.get('ve_id') or request.POST.get('package_id')
        
        if action == 'delete' and ve_id:
            goi = get_object_or_404(ThucDon, id=ve_id, loai_mon='goi_buffet')
            goi.delete()
            messages.success(request, 'Đã xóa gói buffet thành công!')
        
        else:
            ten_mon = request.POST.get('ten_goi') or request.POST.get('ten_mon')
            mo_ta = request.POST.get('mo_ta')
            gia_ban = request.POST.get('gia_ban')
            
            gio_bat_dau = request.POST.get('gio_bat_dau')
            gio_bat_dau = gio_bat_dau if gio_bat_dau else None
            
            gio_ket_thuc = request.POST.get('gio_ket_thuc')
            gio_ket_thuc = gio_ket_thuc if gio_ket_thuc else None
            
            # Extract day fields
            ap_dung_t2 = request.POST.get('ap_dung_t2') == 'on'
            ap_dung_t3 = request.POST.get('ap_dung_t3') == 'on'
            ap_dung_t4 = request.POST.get('ap_dung_t4') == 'on'
            ap_dung_t5 = request.POST.get('ap_dung_t5') == 'on'
            ap_dung_t6 = request.POST.get('ap_dung_t6') == 'on'
            ap_dung_t7 = request.POST.get('ap_dung_t7') == 'on'
            ap_dung_cn = request.POST.get('ap_dung_cn') == 'on'
            
            trang_thai_val = request.POST.get('trang_thai')
            trang_thai = True if trang_thai_val in ['on', 'True', None] else False
            
            if ten_mon and gia_ban:
                if action == 'add':
                    ThucDon.objects.create(
                        ten_mon=ten_mon, loai_mon='goi_buffet', danh_muc='buffet',
                        mo_ta=mo_ta, gia_ban=gia_ban,
                        gio_bat_dau=gio_bat_dau, gio_ket_thuc=gio_ket_thuc,
                        ap_dung_t2=ap_dung_t2, ap_dung_t3=ap_dung_t3, ap_dung_t4=ap_dung_t4,
                        ap_dung_t5=ap_dung_t5, ap_dung_t6=ap_dung_t6, ap_dung_t7=ap_dung_t7,
                        ap_dung_cn=ap_dung_cn, trang_thai=trang_thai
                    )
                    messages.success(request, 'Thêm Vé Buffet mới thành công!')
                    
                elif action == 'edit' and ve_id:
                    goi = get_object_or_404(ThucDon, id=ve_id, loai_mon='goi_buffet')
                    goi.ten_mon = ten_mon
                    if mo_ta: goi.mo_ta = mo_ta
                    goi.gia_ban = gia_ban
                    goi.gio_bat_dau = gio_bat_dau
                    goi.gio_ket_thuc = gio_ket_thuc
                    
                    goi.ap_dung_t2 = ap_dung_t2
                    goi.ap_dung_t3 = ap_dung_t3
                    goi.ap_dung_t4 = ap_dung_t4
                    goi.ap_dung_t5 = ap_dung_t5
                    goi.ap_dung_t6 = ap_dung_t6
                    goi.ap_dung_t7 = ap_dung_t7
                    goi.ap_dung_cn = ap_dung_cn
                    
                    goi.trang_thai = trang_thai
                    goi.save()
                    messages.success(request, 'Cập nhật vé buffet thành công!')

        return redirect('buffet_packages')

    danh_sach_goi = ThucDon.objects.filter(loai_mon='goi_buffet').order_by('-id')
    context = {'danh_sach_goi': danh_sach_goi}
    return render(request, 'buffet/buffet_packages.html', context)

# ==========================================
# 3. QUẢN LÝ ĐỒ UỐNG, PHỤ THU & DANH MỤC
# ==========================================
@login_required(login_url='login')
def menu_manage_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # ------------------------------------------------
        # LOGIC CHO DANH MỤC (Không hỗ trợ tạo mới bằng Model nữa, chỉ fix cứng trong Models.py)
        # ------------------------------------------------
        if action in ['add_category', 'edit_category', 'delete_category']:
            messages.warning(request, "Tính năng quản lý danh mục động đã bị khóa. Vui lòng thêm trong config.")
            return redirect('menu_manage')
            
        # ------------------------------------------------
        # LOGIC CHO ĐỒ UỐNG & DỊCH VỤ
        # ------------------------------------------------
        item_id = request.POST.get('item_id')
        if action == 'delete' and item_id:
            item = get_object_or_404(ThucDon, id=item_id)
            item.delete()
            messages.success(request, "Đã xóa thành công!")
            
        elif action in ['add', 'edit']:
            ten_mon = request.POST.get('ten_mon')
            ma_sku = request.POST.get('ma_sku')
            danh_muc = request.POST.get('danh_muc')
            if not danh_muc: danh_muc = 'nuoc_ngot'
            
            # Tự set loại món
            loai_mon = 'dich_vu' if danh_muc == 'phu_thu' else 'do_uong'
            
            gia_ban = request.POST.get('gia_ban', 0)
            if not gia_ban or gia_ban == '': gia_ban = 0
            gia_von = request.POST.get('gia_von', 0)
            if not gia_von or gia_von == '': gia_von = 0

            # Map form field to trang_thai
            trang_thai = True if request.POST.get('trang_thai') == 'on' or request.POST.get('hien_thi_pos') == 'on' else False
            hinh_anh = request.FILES.get('hinh_anh')

            if action == 'add':
                ThucDon.objects.create(
                    ten_mon=ten_mon, ma_sku=ma_sku, danh_muc=danh_muc, loai_mon=loai_mon,
                    gia_ban=gia_ban, gia_von=gia_von, 
                    trang_thai=trang_thai, hinh_anh=hinh_anh
                )
                messages.success(request, "Thêm mới thành công!")
                
            elif action == 'edit' and item_id:
                item = get_object_or_404(ThucDon, id=item_id)
                item.ten_mon = ten_mon
                item.ma_sku = ma_sku
                item.danh_muc = danh_muc
                item.loai_mon = loai_mon
                item.gia_ban = gia_ban
                item.gia_von = gia_von
                item.trang_thai = trang_thai
                if hinh_anh: item.hinh_anh = hinh_anh
                item.save()
                messages.success(request, "Cập nhật thành công!")

        return redirect('menu_manage') 

    # ------------------------------------------------
    # LẤY DỮ LIỆU HIỂN THỊ (GET)
    # ------------------------------------------------
    danh_sach_item = ThucDon.objects.exclude(loai_mon='goi_buffet').order_by('-ngay_tao')
    
    # Fake danh mục query cho template cũ
    class DummyCat:
        def __init__(self, key, name, icon):
            self.id = key
            self.ten_danh_muc = name
            self.icon = icon
            
    danh_sach_danh_muc = [
        DummyCat(k, v, 'bi-cup-straw' if 'nuoc' in k else 'bi-cash-coin' if 'phu' in k else 'bi-box') 
        for k, v in ThucDon.DANH_MUC_CHOICES if k != 'buffet'
    ]
    
    tong_phu_thu = danh_sach_item.filter(loai_mon='dich_vu').count()
    tong_do_uong = danh_sach_item.filter(loai_mon='do_uong').count()
    het_hang = danh_sach_item.filter(trang_thai=False).count()

    from pos.models import ChiTietHoaDon
    from django.db.models import Sum

    best_seller_data = ChiTietHoaDon.objects.exclude(thuc_don__loai_mon='goi_buffet') \
        .values('ten_mon_luu_tru') \
        .annotate(tong_ban=Sum('so_luong')) \
        .order_by('-tong_ban').first()

    mon_best_seller = best_seller_data['ten_mon_luu_tru'] if best_seller_data else "Chưa có dữ liệu"

    context = {
        'danh_sach_item': danh_sach_item,
        'danh_sach_danh_muc': danh_sach_danh_muc,
        'tong_do_uong': tong_do_uong,
        'tong_phu_thu': tong_phu_thu,
        'het_hang': het_hang,
        'mon_best_seller': mon_best_seller,
    }
    return render(request, 'buffet/menu.html', context)