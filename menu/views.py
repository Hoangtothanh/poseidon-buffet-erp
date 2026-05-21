from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import GoiBuffet, DoUongDichVu, DanhMuc

# ==========================================
# 1. QUẢN LÝ GÓI BUFFET (Đã bổ sung Khung Giờ Bán)
# ==========================================
@login_required(login_url='login')
def buffet_packages_view(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        # Sửa tên trường bắt id cho giống với file ve_buffet.html (ve_id thay vì package_id)
        ve_id = request.POST.get('ve_id') or request.POST.get('package_id')
        
        if action == 'delete' and ve_id:
            goi = get_object_or_404(GoiBuffet, id=ve_id)
            goi.delete()
            messages.success(request, 'Đã xóa gói buffet thành công!')
        
        else:
            ten_goi = request.POST.get('ten_goi')
            mo_ta = request.POST.get('mo_ta')
            gia_ban = request.POST.get('gia_ban')
            
            # CHÚ Ý: Bắt khung giờ bán từ form gửi lên
            gio_bat_dau = request.POST.get('gio_bat_dau')
            gio_bat_dau = gio_bat_dau if gio_bat_dau else '00:00'
            
            gio_ket_thuc = request.POST.get('gio_ket_thuc')
            gio_ket_thuc = gio_ket_thuc if gio_ket_thuc else '23:59'
            
            ngay_ap_dung_list = request.POST.getlist('ngay_ap_dung')
            ngay_ap_dung_str = ",".join(ngay_ap_dung_list) if ngay_ap_dung_list else ""
            
            # Mặc định lấy True nếu form không có trường trang_thai (đối với giao diện ve_buffet.html)
            trang_thai_val = request.POST.get('trang_thai')
            trang_thai = True if trang_thai_val in ['on', 'True', None] else False
            
            if ten_goi and gia_ban:
                if action == 'add':
                    GoiBuffet.objects.create(
                        ten_goi=ten_goi, mo_ta=mo_ta, gia_ban=gia_ban,
                        gio_bat_dau=gio_bat_dau, gio_ket_thuc=gio_ket_thuc,
                        ngay_ap_dung=ngay_ap_dung_str, trang_thai=trang_thai
                    )
                    messages.success(request, 'Thêm Vé Buffet mới thành công!')
                    
                elif action == 'edit' and ve_id:
                    goi = get_object_or_404(GoiBuffet, id=ve_id)
                    goi.ten_goi = ten_goi
                    if mo_ta: goi.mo_ta = mo_ta
                    goi.gia_ban = gia_ban
                    goi.gio_bat_dau = gio_bat_dau
                    goi.gio_ket_thuc = gio_ket_thuc
                    if ngay_ap_dung_str: goi.ngay_ap_dung = ngay_ap_dung_str
                    goi.trang_thai = trang_thai
                    goi.save()
                    messages.success(request, 'Cập nhật khung giờ bán vé thành công!')

        return redirect('buffet_packages')

    danh_sach_goi = GoiBuffet.objects.all().order_by('-id')
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
        # LOGIC CHO DANH MỤC
        # ------------------------------------------------
        cat_id = request.POST.get('cat_id')
        if action == 'delete_category' and cat_id:
            cat = get_object_or_404(DanhMuc, id=cat_id)
            cat.delete()
            messages.success(request, "Đã xóa danh mục thành công!")
            
        elif action in ['add_category', 'edit_category']:
            ten_danh_muc = request.POST.get('ten_danh_muc')
            mo_ta = request.POST.get('mo_ta')
            icon = request.POST.get('icon', 'bi-cup-straw') 
            if not icon: icon = 'bi-cup-straw'
            trang_thai = True if request.POST.get('trang_thai') == 'on' else False

            if action == 'add_category':
                DanhMuc.objects.create(
                    ten_danh_muc=ten_danh_muc, mo_ta=mo_ta, 
                    icon=icon, trang_thai=trang_thai
                )
                messages.success(request, "Thêm danh mục mới thành công!")
                
            elif action == 'edit_category' and cat_id:
                cat = get_object_or_404(DanhMuc, id=cat_id)
                cat.ten_danh_muc = ten_danh_muc
                cat.mo_ta = mo_ta
                cat.icon = icon
                cat.trang_thai = trang_thai
                cat.save()
                messages.success(request, "Cập nhật danh mục thành công!")

        # ------------------------------------------------
        # LOGIC CHO ĐỒ UỐNG & DỊCH VỤ
        # ------------------------------------------------
        item_id = request.POST.get('item_id')
        if action == 'delete' and item_id:
            item = get_object_or_404(DoUongDichVu, id=item_id)
            item.delete()
            messages.success(request, "Đã xóa thành công!")
            
        elif action in ['add', 'edit']:
            ten_mon = request.POST.get('ten_mon')
            ma_sku = request.POST.get('ma_sku')
            
            danh_muc_id = request.POST.get('danh_muc')
            danh_muc_obj = get_object_or_404(DanhMuc, id=danh_muc_id) if danh_muc_id else None
            
            gia_ban = request.POST.get('gia_ban', 0)
            if not gia_ban or gia_ban == '': gia_ban = 0
            
            gia_von = request.POST.get('gia_von', 0)
            if not gia_von or gia_von == '': gia_von = 0

            con_hang = True if request.POST.get('con_hang') == 'on' else False
            hien_thi_pos = True if request.POST.get('hien_thi_pos') == 'on' else False
            hinh_anh = request.FILES.get('hinh_anh')

            if action == 'add':
                DoUongDichVu.objects.create(
                    ten_mon=ten_mon, ma_sku=ma_sku, danh_muc=danh_muc_obj,
                    gia_ban=gia_ban, gia_von=gia_von, con_hang=con_hang,
                    hien_thi_pos=hien_thi_pos, hinh_anh=hinh_anh
                )
                messages.success(request, "Thêm mới thành công!")
                
            elif action == 'edit' and item_id:
                item = get_object_or_404(DoUongDichVu, id=item_id)
                item.ten_mon = ten_mon
                item.ma_sku = ma_sku
                item.danh_muc = danh_muc_obj
                item.gia_ban = gia_ban
                item.gia_von = gia_von
                item.con_hang = con_hang
                item.hien_thi_pos = hien_thi_pos
                if hinh_anh: item.hinh_anh = hinh_anh
                item.save()
                messages.success(request, "Cập nhật thành công!")

        return redirect('menu_manage') 

    # ------------------------------------------------
    # LẤY DỮ LIỆU HIỂN THỊ (GET)
    # ------------------------------------------------
    danh_sach_item = DoUongDichVu.objects.select_related('danh_muc').all().order_by('-ngay_tao')
    danh_sach_danh_muc = DanhMuc.objects.all()
    
    # Lọc Đồ uống vs Phụ thu thông qua Mã SKU
    tong_phu_thu = danh_sach_item.filter(ma_sku__startswith='FEE').count()
    tong_do_uong = danh_sach_item.exclude(ma_sku__startswith='FEE').count()
    het_hang = danh_sach_item.filter(con_hang=False).count()

    context = {
        'danh_sach_item': danh_sach_item,
        'danh_sach_danh_muc': danh_sach_danh_muc,
        'tong_do_uong': tong_do_uong,
        'tong_phu_thu': tong_phu_thu,
        'het_hang': het_hang,
    }
    return render(request, 'buffet/menu.html', context)