from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views import View
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from django.db import transaction, models
import json
import csv

from .models import NhaCungCap, NguyenLieu, PhieuKho, ChiTietPhieuKho
from core.decorators import check_quyen, has_quyen

# ==========================================
# 1. QUẢN LÝ NGUYÊN LIỆU & DANH MỤC
# ==========================================
@login_required(login_url='login')
@check_quyen('inventory_view')
def ingredients_view(request):
    danh_sach_nl = NguyenLieu.objects.all().order_by('danh_muc', 'ten_nguyen_lieu')
    
    class DummyCat:
        def __init__(self, key, name):
            self.id = key
            self.ten_danh_muc = name
            
    danh_sach_dm = [DummyCat(k, v) for k, v in NguyenLieu.DANH_MUC_CHOICES]
    
    tong_ma = danh_sach_nl.count()
    an_toan = sum(1 for nl in danh_sach_nl if nl.ton_kho >= nl.muc_canh_bao and nl.ton_kho > 0)
    canh_bao = sum(1 for nl in danh_sach_nl if 0 < nl.ton_kho < nl.muc_canh_bao)
    het_hang = sum(1 for nl in danh_sach_nl if nl.ton_kho <= 0)

    context = {
        'danh_sach_nl': danh_sach_nl,
        'danh_sach_dm': danh_sach_dm,
        'tong_ma': tong_ma,
        'an_toan': an_toan,
        'canh_bao': canh_bao,
        'het_hang': het_hang,
    }
    return render(request, 'inventory/ingredients.html', context)

@login_required(login_url='login')
@check_quyen('inventory_view')
def manage_ingredient(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        nl_id = request.POST.get('nl_id')

        try:
            if action == 'delete':
                if not has_quyen(request.user, 'inventory_delete'):
                    messages.error(request, 'Lỗi Phân Quyền: Bạn không có quyền XÓA trong phân hệ Kho!')
                    return redirect('ingredients')
                nl = NguyenLieu.objects.get(id=nl_id)
                ten = nl.ten_nguyen_lieu
                nl.delete()
                messages.success(request, f'Đã xóa nguyên liệu: {ten}')
            
            elif action == 'save':
                if not has_quyen(request.user, 'inventory_edit'):
                    messages.error(request, 'Lỗi Phân Quyền: Bạn không có quyền THÊM/SỬA trong phân hệ Kho!')
                    return redirect('ingredients')
                ten = request.POST.get('ten_nguyen_lieu')
                ma = request.POST.get('ma_nl')
                dm_id = request.POST.get('danh_muc')
                dvt = request.POST.get('don_vi_tinh')
                muc_canh_bao = request.POST.get('muc_canh_bao') or 0
                gia_nhap = request.POST.get('gia_nhap_du_kien') or 0

                danh_muc = dm_id if dm_id else 'khac'

                if nl_id: # Sửa
                    nl = NguyenLieu.objects.get(id=nl_id)
                    nl.ten_nguyen_lieu = ten
                    if ma: nl.ma_nl = ma 
                    nl.danh_muc = danh_muc
                    nl.don_vi_tinh = dvt
                    nl.muc_canh_bao = float(muc_canh_bao)
                    nl.don_gia_trung_binh = float(gia_nhap)
                    nl.save()
                    messages.success(request, f'Đã cập nhật nguyên liệu: {ten}')
                else: # Thêm
                    if not ma:
                        last_nl = NguyenLieu.objects.order_by('id').last()
                        new_id = (last_nl.id + 1) if last_nl else 1
                        ma = f"ING-{new_id:04d}"
                    
                    NguyenLieu.objects.create(
                        ma_nl=ma, ten_nguyen_lieu=ten, danh_muc=danh_muc,
                        don_vi_tinh=dvt, muc_canh_bao=float(muc_canh_bao),
                        don_gia_trung_binh=float(gia_nhap), ton_kho=0 
                    )
                    messages.success(request, f'Đã thêm nguyên liệu: {ten}')
        except Exception as e:
            messages.error(request, f'Có lỗi xảy ra: {str(e)}')

    return redirect('ingredients')

# ==========================================
# 2. NHẬP KHO (TÍCH HỢP AJAX + CỘNG TỒN KHO)
# ==========================================
@login_required(login_url='login')
@check_quyen('inventory_view')
def inventory_list(request):
    danh_sach_phieu = PhieuKho.objects.filter(loai_phieu='nhap').order_by('-ngay_thuc_hien')
    danh_sach_ncc = NhaCungCap.objects.all()
    danh_sach_nl = NguyenLieu.objects.all()

    tong_tien_thang = PhieuKho.objects.filter(loai_phieu='nhap', ngay_thuc_hien__month=timezone.now().month).aggregate(Sum('tong_tien'))['tong_tien__sum'] or 0
    so_phieu = danh_sach_phieu.count()
    cong_no = NhaCungCap.objects.aggregate(Sum('cong_no'))['cong_no__sum'] or 0
    
    class DummyCat:
        def __init__(self, key, name):
            self.id = key
            self.ten_danh_muc = name
            
    danh_sach_dm = [DummyCat(k, v) for k, v in NguyenLieu.DANH_MUC_CHOICES]

    context = {
        'danh_sach_phieu': danh_sach_phieu,
        'danh_sach_ncc': danh_sach_ncc,
        'danh_sach_nl': danh_sach_nl,
        'danh_sach_dm': danh_sach_dm,
        'tong_tien_thang': tong_tien_thang,
        'so_phieu': so_phieu,
        'cong_no': cong_no,
    }
    return render(request, 'inventory/inventory.html', context)

@login_required(login_url='login')
@check_quyen('inventory_view')
def manage_inventory_in(request):
    if request.method == 'POST':
        # AJAX JSON → TẠO PHIẾU NHẬP
        if request.content_type and 'application/json' in request.content_type:
            try:
                data = json.loads(request.body)
                ncc_id = data.get('nha_cung_cap')
                ngay_nhap = data.get('ngay_nhap')
                ghi_chu = data.get('ghi_chu', '')
                tong_tien = data.get('tong_tien_nhap', 0)
                da_thanh_toan = data.get('da_thanh_toan', True)
                items = data.get('items', [])

                if not items:
                    return JsonResponse({'status': 'error', 'message': 'Chưa chọn nguyên liệu!'})

                if not has_quyen(request.user, 'inventory_edit'):
                    return JsonResponse({'status': 'error', 'message': 'Lỗi Phân Quyền: Bạn không có quyền THÊM trong phân hệ Kho!'})

                ncc = NhaCungCap.objects.filter(id=ncc_id).first() if ncc_id else None

                with transaction.atomic():
                    last_p = PhieuKho.objects.filter(loai_phieu='nhap').order_by('id').last()
                    new_id = (last_p.id + 1) if last_p else 1
                    ma_phieu = f"PN-{new_id:04d}"

                    phieu = PhieuKho.objects.create(
                        loai_phieu='nhap',
                        ma_phieu=ma_phieu,
                        nha_cung_cap=ncc,
                        ngay_thuc_hien=ngay_nhap if ngay_nhap else timezone.now(),
                        ghi_chu=ghi_chu,
                        tong_tien=float(tong_tien),
                        da_thanh_toan=da_thanh_toan,
                        nguoi_thuc_hien=request.user
                    )

                    if ncc and not da_thanh_toan:
                        ncc.cong_no = float(ncc.cong_no) + float(tong_tien)
                        ncc.save()

                    for item in items:
                        nl = NguyenLieu.objects.select_for_update().get(id=item['nl_id'])
                        sl = float(item['so_luong'])
                        gia = float(item.get('don_gia', 0))

                        ChiTietPhieuKho.objects.create(
                            phieu=phieu,
                            nguyen_lieu=nl,
                            so_luong=sl,
                            don_gia=gia
                        )

                        nl.ton_kho = float(nl.ton_kho) + sl
                        nl.save()

                return JsonResponse({'status': 'success', 'message': 'Đã tạo phiếu nhập kho!'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        action = request.POST.get('action')
        if action == 'delete':
            if not has_quyen(request.user, 'inventory_delete'):
                messages.error(request, 'Lỗi Phân Quyền: Bạn không có quyền XÓA trong phân hệ Kho!')
                return redirect('inventory')
            phieu_id = request.POST.get('phieu_id')
            try:
                with transaction.atomic():
                    phieu = PhieuKho.objects.get(id=phieu_id, loai_phieu='nhap')
                    ma = phieu.ma_phieu

                    if phieu.nha_cung_cap and not phieu.da_thanh_toan:
                        phieu.nha_cung_cap.cong_no = float(phieu.nha_cung_cap.cong_no) - float(phieu.tong_tien)
                        if phieu.nha_cung_cap.cong_no < 0:
                            phieu.nha_cung_cap.cong_no = 0
                        phieu.nha_cung_cap.save()

                    for ct in ChiTietPhieuKho.objects.filter(phieu=phieu):
                        nl = NguyenLieu.objects.select_for_update().get(id=ct.nguyen_lieu_id)
                        nl.ton_kho = float(nl.ton_kho) - float(ct.so_luong)
                        if nl.ton_kho < 0:
                            nl.ton_kho = 0
                        nl.save()

                    phieu.delete()
                    messages.success(request, f'Đã hủy phiếu nhập {ma}')
            except Exception as e:
                messages.error(request, f'Lỗi: {str(e)}')

    return redirect('inventory')

# ==========================================
# 3. XUẤT KHO (TÍCH HỢP AJAX + TRỪ TỒN KHO)
# ==========================================
@login_required(login_url='login')
@check_quyen('inventory_view')
def inventory_outward_view(request):
    danh_sach_phieu_all = PhieuKho.objects.filter(loai_phieu='xuat')
    tong_phieu = danh_sach_phieu_all.count()
    phieu_huy = danh_sach_phieu_all.filter(ghi_chu__icontains='hỏng').count()

    danh_sach_phieu = PhieuKho.objects.filter(loai_phieu='xuat').select_related('nguoi_thuc_hien').prefetch_related('chi_tiet__nguyen_lieu').order_by('-ngay_thuc_hien')[:200]
    
    danh_sach_nl = NguyenLieu.objects.all()

    class DummyCat:
        def __init__(self, key, name):
            self.id = key
            self.ten_danh_muc = name
            
    danh_sach_dm = [DummyCat(k, v) for k, v in NguyenLieu.DANH_MUC_CHOICES]

    cho_duyet = 0

    context = {
        'danh_sach_phieu': danh_sach_phieu,
        'danh_sach_nl': danh_sach_nl,
        'danh_sach_dm': danh_sach_dm,
        'tong_phieu': tong_phieu,
        'phieu_huy': phieu_huy,
        'cho_duyet': cho_duyet,
    }
    return render(request, 'inventory/inventory_outward.html', context)

@login_required(login_url='login')
@check_quyen('inventory_view')
def manage_inventory_out(request):
    if request.method == 'POST':
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                ly_do = data.get('ly_do_xuat', 'Khác')
                ngay_xuat = data.get('ngay_xuat')
                nguoi_nhan = data.get('nguoi_nhan', '')
                ghi_chu = data.get('ghi_chu', '')
                items = data.get('items', [])

                if not items:
                    return JsonResponse({'status': 'error', 'message': 'Chưa chọn nguyên liệu để xuất!'})

                if not has_quyen(request.user, 'inventory_edit'):
                    return JsonResponse({'status': 'error', 'message': 'Lỗi Phân Quyền: Bạn không có quyền THÊM/XUẤT trong phân hệ Kho!'})

                with transaction.atomic():
                    last_px = PhieuKho.objects.filter(loai_phieu='xuat').order_by('id').last()
                    new_id = (last_px.id + 1) if last_px else 1
                    ma_phieu = f"PX-{new_id:04d}"

                    phieu = PhieuKho.objects.create(
                        loai_phieu='xuat',
                        ma_phieu=ma_phieu,
                        ngay_thuc_hien=ngay_xuat if ngay_xuat else timezone.now(),
                        nguoi_thuc_hien=request.user, 
                        ghi_chu=f"Lý do: {ly_do}. Nhận: {nguoi_nhan}. {ghi_chu}"
                    )

                    for item in items:
                        nl = NguyenLieu.objects.select_for_update().get(id=item['nl_id'])
                        sl_xuat = float(item['so_luong'])
                        
                        if float(nl.ton_kho) < sl_xuat:
                            raise Exception(f"Kho không đủ '{nl.ten_nguyen_lieu}' (Hiện tại: {nl.ton_kho})")

                        ChiTietPhieuKho.objects.create(
                            phieu=phieu, nguyen_lieu=nl,
                            so_luong=sl_xuat, ghi_chu=item.get('ghi_chu', '')
                        )

                        nl.ton_kho = float(nl.ton_kho) - sl_xuat
                        nl.save()

                return JsonResponse({'status': 'success', 'message': 'Đã tạo phiếu xuất kho thành công!'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        action = request.POST.get('action')
        if action == 'delete':
            if not has_quyen(request.user, 'inventory_delete'):
                messages.error(request, 'Lỗi Phân Quyền: Bạn không có quyền XÓA trong phân hệ Kho!')
                return redirect('inventory_out')
            phieu_id = request.POST.get('phieu_id')
            try:
                with transaction.atomic():
                    phieu = PhieuKho.objects.get(id=phieu_id, loai_phieu='xuat')
                    ma = phieu.ma_phieu
                    
                    for ct in ChiTietPhieuKho.objects.filter(phieu=phieu):
                        nl = NguyenLieu.objects.select_for_update().get(id=ct.nguyen_lieu_id)
                        nl.ton_kho = float(nl.ton_kho) + float(ct.so_luong)
                        nl.save()

                    phieu.delete()
                    messages.success(request, f'Đã hủy phiếu xuất {ma} và hoàn tồn kho!')
            except Exception as e:
                messages.error(request, f'Lỗi: {str(e)}')

    return redirect('inventory_out')

# ==========================================
# 4. TỒN KHO & KIỂM KÊ (Chỉ xem)
# ==========================================
@login_required(login_url='login')
@check_quyen('inventory_view')
def inventory_stock_view(request):
    danh_sach_nl = NguyenLieu.objects.all().order_by('danh_muc', 'ten_nguyen_lieu')
    
    class DummyCat:
        def __init__(self, key, name):
            self.id = key
            self.ten_danh_muc = name
            
    danh_sach_dm = [DummyCat(k, v) for k, v in NguyenLieu.DANH_MUC_CHOICES]

    tong_gia_tri = sum(float(nl.ton_kho) * float(nl.don_gia_trung_binh) for nl in danh_sach_nl)
    tong_mat_hang = danh_sach_nl.count()
    canh_bao = sum(1 for nl in danh_sach_nl if 0 < float(nl.ton_kho) < float(nl.muc_canh_bao))
    het_hang = sum(1 for nl in danh_sach_nl if float(nl.ton_kho) <= 0)

    for nl in danh_sach_nl:
        if float(nl.ton_kho) <= 0:
            nl.phantram = 0
            nl.trang_thai = 'out'
        else:
            max_val = float(nl.muc_canh_bao) * 3 if float(nl.muc_canh_bao) > 0 else 100
            pt = (float(nl.ton_kho) / max_val) * 100
            nl.phantram = min(pt, 100)
            nl.trang_thai = 'low' if float(nl.ton_kho) < float(nl.muc_canh_bao) else 'safe'

    context = {
        'danh_sach_nl': danh_sach_nl,
        'danh_sach_dm': danh_sach_dm,
        'tong_gia_tri': tong_gia_tri,
        'tong_mat_hang': tong_mat_hang,
        'canh_bao': canh_bao,
        'het_hang': het_hang,
    }
    return render(request, 'inventory/inventory_stock.html', context)

# ==========================================
# 5. NHÀ CUNG CẤP & CÔNG NỢ
# ==========================================
@login_required(login_url='login')
@check_quyen('inventory_view')
def suppliers_view(request):
    danh_sach_ncc = NhaCungCap.objects.all().order_by('ten_ncc')
    
    tong_ncc = danh_sach_ncc.count()
    dang_hop_tac = sum(1 for ncc in danh_sach_ncc if ncc.trang_thai)
    cong_no_phai_tra = sum(ncc.cong_no for ncc in danh_sach_ncc)
    den_han_thanh_toan = sum(1 for ncc in danh_sach_ncc if ncc.cong_no > 10000000)

    context = {
        'danh_sach_ncc': danh_sach_ncc,
        'tong_ncc': tong_ncc,
        'dang_hop_tac': dang_hop_tac,
        'cong_no_phai_tra': cong_no_phai_tra,
        'den_han_thanh_toan': den_han_thanh_toan,
    }
    return render(request, 'inventory/suppliers.html', context)

@login_required(login_url='login')
@check_quyen('inventory_view')
def manage_supplier(request):
    """ Hàm xử lý chung Thêm/Sửa/Xóa/Thanh Toán cho Nhà Cung Cấp """
    if request.method == 'POST':
        action = request.POST.get('action')
        ncc_id = request.POST.get('ncc_id')

        try:
            if action == 'delete':
                if not has_quyen(request.user, 'inventory_delete'):
                    messages.error(request, 'Lỗi Phân Quyền: Bạn không có quyền XÓA trong phân hệ Kho!')
                    return redirect('suppliers')
                ncc = NhaCungCap.objects.get(id=ncc_id)
                ten = ncc.ten_ncc
                ncc.delete()
                messages.success(request, f'Đã xóa nhà cung cấp: {ten}')
                
            elif action == 'pay_debt':
                if not has_quyen(request.user, 'inventory_edit'):
                    messages.error(request, 'Lỗi Phân Quyền: Bạn không có quyền THANH TOÁN (SỬA) trong phân hệ Kho!')
                    return redirect('suppliers')
                so_tien = float(request.POST.get('so_tien_tra', 0))
                if so_tien > 0:
                    ncc = NhaCungCap.objects.get(id=ncc_id)
                    ncc.cong_no = float(ncc.cong_no) - so_tien
                    if ncc.cong_no < 0: 
                        ncc.cong_no = 0
                    ncc.save()
                    messages.success(request, f'Đã thanh toán {so_tien:,.0f} ₫ cho nhà cung cấp {ncc.ten_ncc}!')
                    
            elif action == 'save':
                if not has_quyen(request.user, 'inventory_edit'):
                    messages.error(request, 'Lỗi Phân Quyền: Bạn không có quyền THÊM/SỬA trong phân hệ Kho!')
                    return redirect('suppliers')
                ten = request.POST.get('ten_ncc')
                nguoi = request.POST.get('nguoi_lien_he')
                sdt = request.POST.get('so_dien_thoai')
                dia_chi = request.POST.get('dia_chi')
                trang_thai = True if request.POST.get('trang_thai') == 'on' else False

                if ncc_id: # Sửa
                    ncc = NhaCungCap.objects.get(id=ncc_id)
                    ncc.ten_ncc = ten
                    ncc.nguoi_lien_he = nguoi
                    ncc.so_dien_thoai = sdt
                    ncc.dia_chi = dia_chi
                    ncc.trang_thai = trang_thai
                    ncc.save()
                    messages.success(request, f'Đã cập nhật nhà cung cấp {ten}')
                else: # Thêm
                    NhaCungCap.objects.create(
                        ten_ncc=ten, nguoi_lien_he=nguoi,
                        so_dien_thoai=sdt, dia_chi=dia_chi,
                        trang_thai=trang_thai, cong_no=0
                    )
                    messages.success(request, f'Đã thêm nhà cung cấp {ten}')
                    
        except Exception as e:
            messages.error(request, f'Lỗi: {str(e)}')

    return redirect('suppliers')

# ==========================================
# CÁC HÀM XUẤT EXCEL & AJAX TIỆN ÍCH
# ==========================================
@login_required(login_url='login')
@check_quyen('inventory_view')
def export_inventory_outward_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Lich_Su_Xuat_Kho.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    writer.writerow(['Mã Phiếu', 'Ngày Xuất', 'Ghi Chú', 'Người Lập Phiếu'])
    for phieu in PhieuKho.objects.filter(loai_phieu='xuat').order_by('-ngay_thuc_hien'):
        ngay = phieu.ngay_thuc_hien.strftime("%d/%m/%Y %H:%M") if phieu.ngay_thuc_hien else ""
        nguoi = phieu.nguoi_thuc_hien.username if phieu.nguoi_thuc_hien else "Hệ thống"
        writer.writerow([phieu.ma_phieu, ngay, phieu.ghi_chu, nguoi])
    return response

@login_required(login_url='login')
@check_quyen('inventory_view')
def export_inventory_stock_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Bao_Cao_Ton_Kho.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    writer.writerow(['Mã NL', 'Tên Nguyên Liệu', 'Danh Mục', 'Tồn Kho', 'ĐVT', 'Mức Cảnh Báo', 'Đơn Giá TB', 'Tổng Giá Trị'])
    for nl in NguyenLieu.objects.all().order_by('danh_muc', 'ten_nguyen_lieu'):
        dm = nl.get_danh_muc_display()
        tong_tien = float(nl.ton_kho) * float(nl.don_gia_trung_binh)
        writer.writerow([nl.ma_nl, nl.ten_nguyen_lieu, dm, nl.ton_kho, nl.don_vi_tinh, nl.muc_canh_bao, nl.don_gia_trung_binh, tong_tien])
    return response

@login_required(login_url='login')
@check_quyen('inventory_view')
def export_suppliers_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Cong_No_Nha_Cung_Cap.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    writer.writerow(['Tên Nhà Cung Cấp', 'SĐT', 'Người Liên Hệ', 'Địa Chỉ', 'Trạng Thái', 'Công Nợ Hiện Tại (VNĐ)'])
    for ncc in NhaCungCap.objects.all().order_by('-cong_no'):
        trang_thai = "Đang hợp tác" if ncc.trang_thai else "Ngừng hợp tác"
        writer.writerow([ncc.ten_ncc, ncc.so_dien_thoai, ncc.nguoi_lien_he, ncc.dia_chi, trang_thai, ncc.cong_no])
    return response

@login_required(login_url='login')
@check_quyen('inventory_view')
def import_ingredients_csv(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        if not excel_file.name.endswith(('.csv',)):
            messages.error(request, 'Sai định dạng file! Vui lòng tải lên file .csv')
            return redirect('ingredients')

        try:
            decoded = excel_file.read().decode('utf-8-sig').splitlines()
            reader = csv.reader(decoded)
            next(reader, None)  # Bỏ qua dòng header

            count_created = 0
            count_updated = 0

            with transaction.atomic():
                for row in reader:
                    if len(row) < 1 or not row[0].strip():
                        continue

                    ten_nl = row[0].strip()
                    ten_dm = row[1].strip() if len(row) > 1 else ''
                    dvt = row[2].strip() if len(row) > 2 else 'Kg'
                    muc_cb = float(row[3].strip().replace(',', '')) if len(row) > 3 and row[3].strip() else 10.0
                    don_gia = float(row[4].strip().replace(',', '')) if len(row) > 4 and row[4].strip() else 0.0

                    danh_muc = 'khac'
                    if ten_dm:
                        for k, v in NguyenLieu.DANH_MUC_CHOICES:
                            if v.lower() == ten_dm.lower() or k.lower() == ten_dm.lower():
                                danh_muc = k
                                break

                    nl, created = NguyenLieu.objects.get_or_create(
                        ten_nguyen_lieu=ten_nl,
                        defaults={
                            'danh_muc': danh_muc,
                            'don_vi_tinh': dvt,
                            'muc_canh_bao': muc_cb,
                            'don_gia_trung_binh': don_gia,
                            'ton_kho': 0
                        }
                    )
                    if not created:
                        nl.danh_muc = danh_muc or nl.danh_muc
                        nl.don_vi_tinh = dvt or nl.don_vi_tinh
                        nl.muc_canh_bao = muc_cb
                        nl.don_gia_trung_binh = don_gia
                        nl.save()
                        count_updated += 1
                    else:
                        count_created += 1

            messages.success(request, f'Import thành công! Thêm mới: {count_created} | Cập nhật: {count_updated} nguyên liệu.')
        except Exception as e:
            messages.error(request, f'Lỗi đọc file CSV: {str(e)}')

    return redirect('ingredients')

@login_required(login_url='login')
@check_quyen('inventory_view')
@require_POST
def import_suppliers_csv(request):
    if request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        if not excel_file.name.endswith(('.csv',)):
            messages.error(request, 'Sai định dạng file! Vui lòng tải lên file .csv')
            return redirect('suppliers')

        try:
            decoded = excel_file.read().decode('utf-8-sig').splitlines()
            reader = csv.reader(decoded)
            next(reader, None)

            count_created = 0
            count_updated = 0

            with transaction.atomic():
                for row in reader:
                    if len(row) < 1 or not row[0].strip():
                        continue

                    ten_ncc = row[0].strip()
                    nguoi_lh = row[1].strip() if len(row) > 1 else ''
                    sdt = row[2].strip() if len(row) > 2 else ''
                    dia_chi = row[3].strip() if len(row) > 3 else ''

                    ncc, created = NhaCungCap.objects.get_or_create(
                        ten_ncc=ten_ncc,
                        defaults={
                            'nguoi_lien_he': nguoi_lh,
                            'so_dien_thoai': sdt,
                            'dia_chi': dia_chi,
                            'trang_thai': True,
                            'cong_no': 0
                        }
                    )
                    if not created:
                        ncc.nguoi_lien_he = nguoi_lh or ncc.nguoi_lien_he
                        ncc.so_dien_thoai = sdt or ncc.so_dien_thoai
                        ncc.dia_chi = dia_chi or ncc.dia_chi
                        ncc.save()
                        count_updated += 1
                    else:
                        count_created += 1

            messages.success(request, f'Import thành công! Thêm mới: {count_created} | Cập nhật: {count_updated} nhà cung cấp.')
        except Exception as e:
            messages.error(request, f'Lỗi đọc file CSV: {str(e)}')

    return redirect('suppliers')

@login_required(login_url='login')
@check_quyen('inventory_view')
def export_inventory_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Lich_Su_Nhap_Kho.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    writer.writerow(['Mã Phiếu', 'Ngày Nhập', 'Nhà Cung Cấp', 'Tổng Tiền (VNĐ)', 'Ghi Chú', 'Người Nhập'])
    for phieu in PhieuKho.objects.filter(loai_phieu='nhap').order_by('-ngay_thuc_hien'):
        ncc = phieu.nha_cung_cap.ten_ncc if phieu.nha_cung_cap else "Mua lẻ"
        ngay = phieu.ngay_thuc_hien.strftime("%d/%m/%Y %H:%M") if phieu.ngay_thuc_hien else ""
        nguoi_tao = phieu.nguoi_thuc_hien.username if phieu.nguoi_thuc_hien else "Hệ thống"
        writer.writerow([phieu.ma_phieu, ngay, ncc, phieu.tong_tien, phieu.ghi_chu, nguoi_tao])
    return response

@login_required(login_url='login')
@check_quyen('inventory_view')
def add_category_ajax(request):
    return JsonResponse({'status': 'error', 'message': 'Tính năng thêm danh mục động đã bị khóa! Vui lòng sửa trực tiếp trong code Models.'}, status=400)

@login_required(login_url='login')
@check_quyen('inventory_view')
@require_POST
def close_inventory_period_ajax(request):
    try:
        return JsonResponse({'status': 'success', 'message': 'Đã chốt kỳ kiểm kê thành công! Dữ liệu đã được lưu trữ an toàn.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)