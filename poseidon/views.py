import csv
import json # Thư viện đọc dữ liệu từ Javascript gửi lên
from datetime import date, timedelta

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Sum, F, Q

# Import các Model từ các app (Bạn có thể cần kiểm tra lại đường dẫn model nếu bị lỗi)
from inventory.models import HaiSan
from orders.models import HoaDon, DoUongDichVu, ChiTietDoUong, CaiDatHeThong
from tables.models import BanAn, PhieuDatBan
from ai_engine.models import DuBao

# ==========================================
# 1. AUTH (ĐĂNG NHẬP)
# ==========================================
def login_view(request): # Đổi tên thành login_view cho đồng bộ
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        ten_dang_nhap = request.POST.get('username')
        mat_khau = request.POST.get('password')
        user = authenticate(request, username=ten_dang_nhap, password=mat_khau)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Tài khoản hoặc mật khẩu không chính xác!')
    return render(request, 'auth/login.html')

# ==========================================
# 2. DASHBOARD (TỔNG QUAN)
# ==========================================
@login_required(login_url='login')
def dashboard_view(request):
    # Tránh lỗi nếu database chưa có dữ liệu dự báo
    du_bao = DuBao.objects.order_by('-id').first() if DuBao.objects.exists() else None
    ton_kho = HaiSan.objects.all()
    today = date.today()
    labels_ngay = []
    data_khach = []
    for i in range(29, -1, -1):
        ngay = today - timedelta(days=i)
        labels_ngay.append(ngay.strftime('%d/%m'))
        tong_khach = HoaDon.objects.filter(ngay_tao__date=ngay).aggregate(
        tong=Sum(F('so_nguoi_lon') + F('so_tre_em')))
        khach_trong_ngay = tong_khach['tong'] or 0
        data_khach.append(khach_trong_ngay)
    return render(request, 'dashboard/dashboard.html', {
        'du_bao': du_bao, 'ton_kho': ton_kho, 'labels_ngay': labels_ngay, 'data_khach': data_khach
    })

# ==========================================
# 3. POS & KHÁCH HÀNG QUÉT QR
# ==========================================
@login_required(login_url='login')
def pos_view(request):
    # NẾU LÀ GIAO DỊCH LƯU ĐƠN (AJAX POST)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ban_id = data.get('ban_id')
            so_nguoi_lon = int(data.get('so_nguoi_lon', 0))
            so_tre_em = int(data.get('so_tre_em', 0))
            so_tre_em_free = int(data.get('so_tre_em_free', 0))
            drinks = data.get('drinks', []) 

            if not ban_id:
                return JsonResponse({'status': 'error', 'message': 'Vui lòng chọn bàn!'})
            if so_nguoi_lon == 0 and so_tre_em == 0:
                return JsonResponse({'status': 'error', 'message': 'Chưa nhập số lượng khách!'})

            ban = BanAn.objects.get(id=ban_id)
            
            # TẠO HÓA ĐƠN
            hoa_don = HoaDon.objects.create(
                ban=ban,
                so_nguoi_lon=so_nguoi_lon,
                so_tre_em=so_tre_em,
                so_tre_em_free=so_tre_em_free
            )
            ban.trang_thai = 'dang_an'
            ban.save()

            # THÊM ĐỒ UỐNG
            for d in drinks:
                do_uong = DoUongDichVu.objects.get(id=d['id'])
                ChiTietDoUong.objects.create(
                    hoa_don=hoa_don,
                    do_uong=do_uong,
                    so_luong=d['qty']
                )
            
            hoa_don.save()

            return JsonResponse({
                'status': 'success', 
                'message': 'Đã tạo hóa đơn thành công!',
                'invoice_id': hoa_don.id,
                'tong_tien': hoa_don.tong_tien
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Lỗi hệ thống: {str(e)}'})

    ds_ban = BanAn.objects.all()
    ds_do_uong = DoUongDichVu.objects.all()
    return render(request, 'pos/pos.html', {
        'ds_ban': ds_ban, 
        'ds_do_uong': ds_do_uong
    })

def customer_menu_view(request):
    """Màn hình quét QR Menu cho Khách (Không cần login vì khách dùng)"""
    return render(request, 'customers/customer_menu.html')

# ==========================================
# 4. HÓA ĐƠN (INVOICES) & LỊCH SỬ THU NGÂN
# ==========================================
@login_required(login_url='login')
def invoice_list(request):
    query = request.GET.get('q', '')
    danh_sach_hoa_don = HoaDon.objects.all().order_by('-ngay_tao', '-id')
    
    if query:
        if query.isdigit(): 
            danh_sach_hoa_don = danh_sach_hoa_don.filter(id=query)

    tong_so_don = danh_sach_hoa_don.count()
    paginator = Paginator(danh_sach_hoa_don, 50) 
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'tong_so_don': tong_so_don,
        'query': query,
    }
    return render(request, 'pos/invoices.html', context) # Đã trỏ vào thư mục pos/

@login_required(login_url='login')
def invoice_detail_ajax(request, pk):
    try:
        hd = HoaDon.objects.get(pk=pk)
        chi_tiet_list = []
        for ct in hd.chitiet.all():
            chi_tiet_list.append({
                'ten_mon': ct.hai_san.ten_mat_hang if ct.hai_san else "Nguyên liệu",
                'so_luong': ct.so_luong
            })
        
        data = {
            'status': 'success',
            'id': hd.id,
            'ngay_tao': hd.ngay_tao.strftime("%H:%M - %d/%m/%Y"),
            'so_khach': hd.so_nguoi_lon + hd.so_tre_em,   
            'goi_buffet': str(hd.goi_buffet) if hd.goi_buffet else "Gói Mặc Định",
            'ban': str(hd.ban) if hd.ban else "Bàn Tự Do",
            'danh_sach_mon': chi_tiet_list
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required(login_url='login')
def payments_view(request):
    return render(request, 'pos/payments.html')

# ==========================================
# 5. KHÁCH & BÀN (TABLES & BOOKINGS)
# ==========================================
@login_required(login_url='login')
def tables_view(request): # Đổi tên cho đồng bộ với urls
    danh_sach_ban = BanAn.objects.all().order_by('khu_vuc', 'ten_ban')
    context = {
        'danh_sach_ban': danh_sach_ban,
        'tong_ban': danh_sach_ban.count(),
        'ban_trong': danh_sach_ban.filter(trang_thai='trong').count(),
        'ban_dang_an': danh_sach_ban.filter(trang_thai='dang_an').count(),
        'ban_da_dat': danh_sach_ban.filter(trang_thai='da_dat').count(),
    }
    return render(request, 'pos/payments.html')

@login_required(login_url='login')
def clear_table_ajax(request, ban_id):
    if request.method == 'POST':
        try:
            ban = BanAn.objects.get(id=ban_id)
            ban.trang_thai = 'trong' 
            ban.save()
            return JsonResponse({'status': 'success', 'message': f'Đã dọn xong {ban.ten_ban}! Sẵn sàng đón khách.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

@login_required(login_url='login')
def table_zones_view(request):
    return render(request, 'customers/table_zones.html')

@login_required(login_url='login')
def customers_view(request):
    return render(request, 'customers/customers.html')

@login_required(login_url='login')
def booking_list(request): # Có thể đổi thành bookings_view ở urls.py
    ds_dat_ban = PhieuDatBan.objects.all().order_by('-thoi_gian_den')
    ban_trong = BanAn.objects.filter(trang_thai='trong')
    context = {
        'ds_dat_ban': ds_dat_ban,
        'ban_trong': ban_trong,
        'cho_xac_nhan': ds_dat_ban.filter(trang_thai='cho_xac_nhan').count(),
        'da_xac_nhan': ds_dat_ban.filter(trang_thai='da_xac_nhan').count(),
    }
    return render(request, 'customers/bookings.html', context)

@login_required(login_url='login')
def update_booking_status_ajax(request, pk):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            ban_id = data.get('ban_id')

            booking = PhieuDatBan.objects.get(pk=pk)
            booking.trang_thai = new_status
            
            if ban_id:
                ban = BanAn.objects.get(id=ban_id)
                booking.ban = ban
                if new_status == 'da_xac_nhan':
                    ban.trang_thai = 'da_dat'
                    ban.save()
                elif new_status == 'hoan_thanh':
                    ban.trang_thai = 'dang_an'
                    ban.save()
            elif new_status == 'huy' and booking.ban:
                booking.ban.trang_thai = 'trong'
                booking.ban.save()

            booking.save()
            return JsonResponse({'status': 'success', 'message': 'Đã cập nhật trạng thái Đặt bàn!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

# ==========================================
# 6. QUẢN LÝ GÓI BUFFET & LINE
# ==========================================
@login_required(login_url='login')
def buffet_packages_view(request):
    return render(request, 'buffet/buffet_packages.html')

@login_required(login_url='login')
def buffet_dishes_view(request):
    return render(request, 'buffet/buffet_dishes.html')

@login_required(login_url='login')
def line_stations_view(request):
    return render(request, 'buffet/line_stations.html')

# ==========================================
# 7. QUẢN LÝ THỰC ĐƠN ALACARTE
# ==========================================
@login_required(login_url='login')
def menu_manage_view(request):
    return render(request, 'menu/menu.html')

@login_required(login_url='login')
def menu_categories_view(request):
    return render(request, 'menu/menu_categories.html')

# ==========================================
# 8. KHO NGUYÊN LIỆU (INVENTORY)
# ==========================================
@login_required(login_url='login')
def ingredients_view(request):
    return render(request, 'inventory/ingredients.html')

@login_required(login_url='login')
def inventory_list(request): # Thường tương ứng với 'inventory_in.html'
    ds_hai_san = HaiSan.objects.all().order_by('-ton_kho')
    tong_khoi_luong = sum(item.ton_kho for item in ds_hai_san)
    context = {
        'ds_hai_san': ds_hai_san,
        'tong_mat_hang': ds_hai_san.count(),
        'tong_khoi_luong': round(tong_khoi_luong, 1)
    }
    return render(request, 'inventory/inventory.html', context)

@login_required(login_url='login')
def inventory_outward_view(request):
    return render(request, 'inventory/inventory_outward.html')

@login_required(login_url='login')
def inventory_stock_view(request):
    return render(request, 'inventory/inventory_stock.html')

@login_required(login_url='login')
def suppliers_view(request):
    return render(request, 'inventory/suppliers.html')

@login_required(login_url='login')
def export_inventory_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Ton_Kho_Poseidon.csv"'
    response.write(u'\ufeff'.encode('utf8'))
    writer = csv.writer(response)
    writer.writerow(['Mã ID', 'Tên Nguyên Liệu', 'Tồn Kho (Kg)', 'Mức Cảnh Báo'])
    
    for item in HaiSan.objects.all().order_by('-ton_kho'):
        trang_thai = "Cần nhập gấp" if item.ton_kho <= 5 else "Chuẩn bị nhập" if item.ton_kho <= 15 else "Dồi dào"
        writer.writerow([f'#{item.id}', item.ten_mat_hang, item.ton_kho, trang_thai])
    return response

@method_decorator(login_required(login_url='login'), name='dispatch')
class InventoryAjaxView(View):
    def post(self, request, pk=None):
        ten = request.POST.get('ten_mat_hang')
        so_luong = request.POST.get('ton_kho')
        if not ten or not so_luong:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng nhập đầy đủ tên và số lượng!'})

        try:
            if pk:
                item = HaiSan.objects.get(pk=pk)
                item.ten_mat_hang = ten
                item.ton_kho = float(so_luong)
                item.save()
                return JsonResponse({'status': 'success', 'message': f'Đã cập nhật "{ten}" thành {so_luong} Kg!'})
            else:
                DanhMucModel = HaiSan._meta.get_field('danh_muc').related_model
                danh_muc_mac_dinh = DanhMucModel.objects.first()
                if not danh_muc_mac_dinh:
                    return JsonResponse({'status': 'error', 'message': 'Lỗi: Hãy tạo ít nhất 1 Danh Mục trong Admin trước!'})
                
                HaiSan.objects.create(ten_mat_hang=ten, ton_kho=float(so_luong), danh_muc=danh_muc_mac_dinh)
                return JsonResponse({'status': 'success', 'message': f'Đã thêm "{ten}" vào kho!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Lỗi hệ thống: {str(e)}'})

    def delete(self, request, pk=None):
        if not pk:
            return JsonResponse({'status': 'error', 'message': 'Không tìm thấy ID!'})
        try:
            item = HaiSan.objects.get(pk=pk)
            ten = item.ten_mat_hang
            item.delete()
            return JsonResponse({'status': 'success', 'message': f'Đã xóa "{ten}"!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

# ==========================================
# 9. NHÂN SỰ
# ==========================================
@login_required(login_url='login')
def employees_view(request):
    return render(request, 'employees/employees.html')

@login_required(login_url='login')
def shifts_view(request):
    return render(request, 'employees/shifts.html')

# ==========================================
# 10. BÁO CÁO TÀI CHÍNH
# ==========================================
@login_required(login_url='login')
def revenue_report_view(request):
    return render(request, 'reports/report_revenue.html')

@login_required(login_url='login')
def report_consumption_view(request):
    return render(request, 'reports/report_consumption.html')

@login_required(login_url='login')
def report_inventory_view(request):
    return render(request, 'reports/report_inventory.html')

@login_required(login_url='login')
def report_performance_view(request):
    return render(request, 'reports/report_performance.html')

# ==========================================
# 11. AI ENGINE (PHÂN TÍCH & TỐI ƯU)
# ==========================================
@login_required(login_url='login')
def ai_prediction_view(request):
    return render(request, 'ai/ai_prediction.html')

@login_required(login_url='login')
def ai_customer_traffic_view(request):
    return render(request, 'ai/ai_customer_traffic.html')

@login_required(login_url='login')
def ai_menu_optimization_view(request):
    return render(request, 'ai/ai_menu_optimization.html')

# ==========================================
# 12. CÀI ĐẶT HỆ THỐNG
# ==========================================
@login_required(login_url='login')
def settings_view(request):
    # Lấy cấu hình ra (nếu chưa có thì tự động tạo mới 1 cái mặc định)
    setting, created = CaiDatHeThong.objects.get_or_create(pk=1)

    if request.method == 'POST':
        form_type = request.POST.get('form_type') 

        if form_type == 'info':
            setting.ten_quan = request.POST.get('ten_quan')
            setting.dia_chi = request.POST.get('dia_chi')
            setting.so_dien_thoai = request.POST.get('so_dien_thoai')
            setting.logo_url = request.POST.get('logo_url')
            messages.success(request, "Đã cập nhật Thông tin quán!")
            
        elif form_type == 'tax':
            setting.thue_vat = request.POST.get('thue_vat', 0)
            setting.phi_phuc_vu = request.POST.get('phi_phuc_vu', 0)
            messages.success(request, "Đã cập nhật Thuế & Phí!")
            
        elif form_type == 'bank':
            setting.ngan_hang = request.POST.get('ngan_hang')
            setting.so_tai_khoan = request.POST.get('so_tai_khoan')
            setting.chu_tai_khoan = request.POST.get('chu_tai_khoan')
            messages.success(request, "Đã cập nhật Thông tin chuyển khoản!")

        setting.save()
        return redirect('settings')

    return render(request, 'system/settings.html', {'setting': setting})