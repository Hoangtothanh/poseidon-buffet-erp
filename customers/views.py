from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.decorators import check_quyen
from django.utils.dateparse import parse_date
from django.utils import timezone
from .models import Voucher, KhachHang
import csv
from django.http import HttpResponse
from django.db import transaction

# ==========================================
# PHÂN HỆ 1: QUẢN LÝ KHÁCH HÀNG
# ==========================================
@login_required(login_url='login')
@check_quyen('system_all')
def customers_view(request):
    # Lấy toàn bộ danh sách khách hàng từ DB, sắp xếp người mới nhất lên đầu
    khach_hang_list = KhachHang.objects.all().order_by('-ngay_tao')
    
    # Tính toán các chỉ số KPI
    tong_kh = khach_hang_list.count()
    kh_vip = khach_hang_list.filter(diem_tich_luy__gte=2000).count()
    
    # 2 biến giả định cho biểu đồ (Vì cần liên kết với Hóa đơn POS)
    khach_den_hom_nay = 0
    khach_sinh_nhat = 0
    
    # ĐÓNG GÓI DỮ LIỆU ĐÚNG TÊN BIẾN ĐỂ TRUYỀN RA HTML
    context = {
        'khach_hang_list': khach_hang_list,
        'tong_kh': tong_kh,
        'kh_vip': kh_vip,
        'khach_den_hom_nay': khach_den_hom_nay,
        'khach_sinh_nhat': khach_sinh_nhat,
    }
    return render(request, 'customers/customers.html', context)

@login_required(login_url='login')
@check_quyen('system_all')
def save_customer(request):
    """ Xử lý Thêm mới hoặc Cập nhật Khách Hàng """
    if request.method == 'POST':
        kh_id = request.POST.get('kh_id')
        ho_ten = request.POST.get('ho_ten', '').strip()
        so_dien_thoai = request.POST.get('so_dien_thoai', '').strip()
        email = request.POST.get('email', '').strip()
        ngay_sinh = request.POST.get('ngay_sinh')
        is_active = request.POST.get('is_active') == 'on'

        try:
            if kh_id: # CẬP NHẬT
                kh = get_object_or_404(KhachHang, id=kh_id)
                if KhachHang.objects.filter(so_dien_thoai=so_dien_thoai).exclude(id=kh_id).exists():
                    messages.error(request, "Số điện thoại này đã được đăng ký!")
                    return redirect('customers')
                
                kh.ho_ten = ho_ten
                kh.so_dien_thoai = so_dien_thoai
                kh.email = email
                kh.ngay_sinh = parse_date(ngay_sinh) if ngay_sinh else None
                kh.is_active = is_active
                kh.save()
                messages.success(request, f"Đã cập nhật khách hàng {ho_ten} thành công!")
                
            else: # THÊM MỚI
                if KhachHang.objects.filter(so_dien_thoai=so_dien_thoai).exists():
                    messages.error(request, "Số điện thoại này đã được đăng ký!")
                    return redirect('customers')
                    
                KhachHang.objects.create(
                    ho_ten=ho_ten,
                    so_dien_thoai=so_dien_thoai,
                    email=email,
                    ngay_sinh=parse_date(ngay_sinh) if ngay_sinh else None,
                    is_active=is_active
                )
                messages.success(request, f"Đã thêm khách hàng {ho_ten} thành công!")
        except Exception as e:
            messages.error(request, f"Lỗi: {str(e)}")
            
    return redirect('customers')

@login_required(login_url='login')
@check_quyen('system_all')
def delete_customer(request, kh_id):
    """ Xử lý xóa Khách Hàng """
    if request.method == 'POST':
        kh = get_object_or_404(KhachHang, id=kh_id)
        ten = kh.ho_ten
        kh.delete()
        messages.success(request, f"Đã xóa dữ liệu khách hàng {ten}.")
    return redirect('customers')


# ==========================================
# PHÂN HỆ 2: QUẢN LÝ KHUYẾN MÃI (VOUCHER)
# ==========================================
@login_required(login_url='login')
@check_quyen('system_all')
def vouchers_view(request):
    vouchers = Voucher.objects.all().order_by('-ngay_tao')
    
    context = {
        'vouchers': vouchers
    }
    return render(request, 'customers/vouchers.html', context)

@login_required(login_url='login')
@check_quyen('system_all')
def save_voucher(request):
    """ Xử lý Thêm mới hoặc Cập nhật Voucher """
    if request.method == 'POST':
        voucher_id = request.POST.get('voucher_id')
        ma_code = request.POST.get('ma_code', '').strip().upper()
        muc_giam = request.POST.get('muc_giam', '').strip()
        dieu_kien_toi_thieu = request.POST.get('dieu_kien_toi_thieu', 0)
        ngay_het_han = request.POST.get('ngay_het_han')
        trang_thai = request.POST.get('trang_thai') == 'on' 
        
        if not dieu_kien_toi_thieu:
            dieu_kien_toi_thieu = 0

        try:
            if voucher_id: # SỬA VOUCHER
                voucher = get_object_or_404(Voucher, id=voucher_id)
                
                # Check trùng ma_code
                if Voucher.objects.filter(ma_code=ma_code).exclude(id=voucher_id).exists():
                     messages.error(request, f"Mã khuyến mãi '{ma_code}' đã tồn tại!")
                     return redirect('vouchers')
                     
                voucher.ma_code = ma_code
                voucher.muc_giam = muc_giam
                voucher.dieu_kien_toi_thieu = dieu_kien_toi_thieu
                voucher.ngay_het_han = parse_date(ngay_het_han)
                voucher.trang_thai = trang_thai
                voucher.save()
                messages.success(request, f"Đã cập nhật mã {ma_code} thành công!")
                
            else: # THÊM MỚI
                if Voucher.objects.filter(ma_code=ma_code).exists():
                     messages.error(request, f"Mã khuyến mãi '{ma_code}' đã tồn tại!")
                     return redirect('vouchers')
                     
                Voucher.objects.create(
                    ma_code=ma_code,
                    muc_giam=muc_giam,
                    dieu_kien_toi_thieu=dieu_kien_toi_thieu,
                    ngay_het_han=parse_date(ngay_het_han),
                    trang_thai=trang_thai
                )
                messages.success(request, f"Đã tạo mới mã {ma_code} thành công!")
                
        except Exception as e:
            messages.error(request, f"Đã xảy ra lỗi: {str(e)}")
            
    return redirect('vouchers')

@login_required(login_url='login')
@check_quyen('system_all')
def delete_voucher(request, voucher_id):
    """ Xử lý xóa Voucher """
    if request.method == 'POST':
        voucher = get_object_or_404(Voucher, id=voucher_id)
        code_name = voucher.ma_code
        voucher.delete()
        messages.success(request, f"Đã xóa mã khuyến mãi {code_name}.")
        
    return redirect('vouchers')

@login_required(login_url='login')
@check_quyen('system_all')
def export_customers(request):
    """ Hàm kết xuất danh sách Khách hàng ra file CSV (Mở bằng Excel) """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="danh_sach_khach_hang.csv"'
    
    # Ghi ký tự BOM để Excel đọc tiếng Việt không bị lỗi font
    response.write('\ufeff'.encode('utf8')) 
    writer = csv.writer(response)
    
    # Viết dòng tiêu đề
    writer.writerow(['Họ và Tên', 'Số điện thoại', 'Email', 'Ngày sinh', 'Hạng thẻ', 'Điểm tích lũy', 'Trạng thái'])
    
    # Đổ dữ liệu
    khach_hangs = KhachHang.objects.all().order_by('-ngay_tao')
    for kh in khach_hangs:
        ngay_sinh_str = kh.ngay_sinh.strftime('%d/%m/%Y') if kh.ngay_sinh else ''
        trang_thai_str = 'Hoạt động' if kh.is_active else 'Đã khóa'
        writer.writerow([kh.ho_ten, kh.so_dien_thoai, kh.email, ngay_sinh_str, kh.hang_the.title(), kh.diem_tich_luy, trang_thai_str])
        
    return response

@login_required(login_url='login')
@check_quyen('system_all')
def import_customers(request):
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


def ai_goi_y_voucher(khach_hang, tong_tien=0):
    """
    AI Gợi ý voucher dựa trên giá trị hóa đơn và hạng thẻ khách hàng.
    Logic: Gợi ý tất cả voucher còn hiệu lực mà khách ĐỦ điều kiện áp dụng.
    Ưu tiên voucher phù hợp hạng thẻ hơn (sắp xếp theo mức giảm cao nhất).
    Trả về tối đa 3 gợi ý.
    """
    from django.db.models import Q
    from decimal import Decimal

    today = timezone.now().date()
    tong_tien_dec = Decimal(str(tong_tien))
    hang_the = (getattr(khach_hang, 'hang_the', '') or '').lower()

    # Lấy toàn bộ voucher đang hoạt động và còn hạn
    vouchers = Voucher.objects.filter(
        trang_thai=True,
        ngay_het_han__gte=today
    )

    goi_y = []
    for v in vouchers:
        dieu_kien = Decimal(str(v.dieu_kien_toi_thieu or 0))

        # ✅ Điều kiện 1: Tổng hóa đơn đủ điều kiện tối thiểu của voucher
        du_dieu_kien_tien = (tong_tien_dec >= dieu_kien)

        # ✅ Điều kiện 2 (tuỳ chọn): Gợi ý thêm voucher gần đủ điều kiện
        # (thiếu tối đa 20% nữa là đủ → upsell khéo léo)
        gan_du_dieu_kien = (dieu_kien > 0 and tong_tien_dec >= dieu_kien * Decimal('0.8'))

        if du_dieu_kien_tien or (gan_du_dieu_kien and dieu_kien > 0):
            # Thêm thuộc tính phụ để sort
            v._score = 0
            ma_upper = v.ma_code.upper()

            # Ưu tiên voucher phù hợp hạng thẻ
            if hang_the in ['kim cương', 'kim cuong'] and any(k in ma_upper for k in ['VIP', 'DIAMOND', 'KIM']):
                v._score += 10
            elif hang_the == 'vàng' and any(k in ma_upper for k in ['GOLD', 'VANG', 'VIP']):
                v._score += 8
            elif hang_the == 'bạc' and any(k in ma_upper for k in ['SILVER', 'BAC']):
                v._score += 6

            # Ưu tiên voucher đủ điều kiện (không phải chỉ gần đủ)
            if du_dieu_kien_tien:
                v._score += 5

            # Gắn cờ "gần đủ" để UI có thể hiển thị thông báo khuyến khích
            v._gan_du = not du_dieu_kien_tien and gan_du_dieu_kien
            goi_y.append(v)

    # Sắp xếp: score cao nhất → nhiều nhất, rồi theo điều kiện tối thiểu thấp nhất
    goi_y.sort(key=lambda x: (-x._score, x.dieu_kien_toi_thieu or 0))

    return goi_y[:3]  # Tối đa 3 gợi ý