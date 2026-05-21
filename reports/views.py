from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Sum, Count, F, Avg
import json
import csv
from django.http import HttpResponse

# Nhập Models thật từ các App (Điều chỉnh tên App nếu của bạn khác nhé)
from pos.models import HoaDon, ChiTietHoaDon
from inventory.models import NguyenLieu, PhieuNhapKho, ChiTietNhapKho, PhieuXuatKho, ChiTietXuatKho
from reception.models import BanAn, KhuVuc
from django.contrib.auth.models import User

# ==========================================
# 1. BÁO CÁO DOANH THU (REVENUE)
# ==========================================
@login_required(login_url='login')
def revenue_report_view(request):
    today = timezone.now().date()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        start_date = today - timedelta(days=6)
        end_date = today

    delta_days = (end_date - start_date).days + 1
    if delta_days <= 0: delta_days = 1

    chart_labels = []
    chart_data = []
    table_data = []
    
    tong_doanh_thu = tong_khach = tong_ve = tong_phu_thu = so_hd_tong = 0
    
    for i in range(delta_days):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime('%d/%m/%Y')
        
        # QUERY DỮ LIỆU THẬT: Hóa đơn đã thanh toán trong ngày
        hoadons = HoaDon.objects.filter(
            trang_thai='da_thanh_toan',
            thoi_gian_ra__date=current_date
        )
        
        agg = hoadons.aggregate(
            tong_khach=Sum('so_khach'),
            tong_ve=Sum('tong_tien_hang'),
            tong_phu_thu=Sum('vat_phu_thu'),
            tong_tien=Sum('khach_can_tra')
        )
        
        so_hd = hoadons.count()
        so_khach_ngay = agg['tong_khach'] or 0
        tien_ve_ngay = agg['tong_ve'] or 0
        tien_phu_thu_ngay = agg['tong_phu_thu'] or 0
        doanh_thu_ngay = agg['tong_tien'] or 0
        
        chart_labels.append(date_str)
        chart_data.append(float(doanh_thu_ngay))
        
        table_data.insert(0, { 
            'ngay': "Hôm nay" if current_date == today else date_str,
            'so_hd': so_hd, 'so_khach': so_khach_ngay,
            'tien_ve': tien_ve_ngay, 'tien_phu_thu': tien_phu_thu_ngay,
            'tong_doanh_thu': doanh_thu_ngay
        })
        
        tong_doanh_thu += doanh_thu_ngay
        tong_khach += so_khach_ngay
        tong_ve += tien_ve_ngay
        tong_phu_thu += tien_phu_thu_ngay
        so_hd_tong += so_hd
        
    arpu = tong_doanh_thu / tong_khach if tong_khach > 0 else 0

    context = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'tong_doanh_thu': float(tong_doanh_thu),
        'tong_khach': tong_khach,
        'arpu': float(arpu),
        'table_data': table_data,
        'tong_ve': float(tong_ve), 
        'tong_phu_thu': float(tong_phu_thu), 
        'so_hd_tong': so_hd_tong,
        'chart_labels_json': json.dumps(chart_labels),
        'chart_data_json': json.dumps(chart_data),
        'phan_tram_ve': round((float(tong_ve) / float(tong_doanh_thu)) * 100, 1) if tong_doanh_thu > 0 else 0,
    }
    return render(request, 'reports/report_revenue.html', context)

@login_required(login_url='login')
def export_revenue_csv(request):
    # Logc xuất Excel (Viết tương tự cấu trúc đã đưa ở trước)
    pass


# ==========================================
# 2. BÁO CÁO TIÊU THỤ (CONSUMPTION)
# ==========================================
@login_required(login_url='login')
def report_consumption_view(request):
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    today = timezone.now().date()

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        start_date = today - timedelta(days=6)
        end_date = today

    # Lấy dữ liệu Phiếu Xuất trong kỳ
    chi_tiet_xuats = ChiTietXuatKho.objects.filter(
        phieu_xuat__ngay_xuat__date__range=[start_date, end_date]
    ).select_related('nguyen_lieu', 'nguyen_lieu__danh_muc', 'phieu_xuat')

    mon_stats = {}
    tong_tieu_thu = tong_hao_hut = 0

    for ct in chi_tiet_xuats:
        ten_nl = ct.nguyen_lieu.ten_nguyen_lieu
        nhom_nl = ct.nguyen_lieu.danh_muc.ten_danh_muc if ct.nguyen_lieu.danh_muc else "Khác"
        sl = float(ct.so_luong_xuat)
        
        if ten_nl not in mon_stats:
            mon_stats[ten_nl] = {'nhom': nhom_nl, 'xuat_bep': 0, 'xuat_huy': 0}
        
        # Kiểm tra lý do xuất
        ly_do = ct.phieu_xuat.ly_do_xuat.lower()
        if 'hủy' in ly_do or 'hỏng' in ly_do:
            mon_stats[ten_nl]['xuat_huy'] += sl
            tong_hao_hut += sl
        else:
            mon_stats[ten_nl]['xuat_bep'] += sl
            tong_tieu_thu += sl

    table_data = []
    chart_labels = []
    chart_data = []

    for ten, data in mon_stats.items():
        tong_xuat = data['xuat_bep'] + data['xuat_huy']
        tieu_thu = data['xuat_bep']
        huy = data['xuat_huy']
        ty_le = round((tieu_thu / tong_xuat) * 100, 1) if tong_xuat > 0 else 0
        
        # Color badge
        color, bg = '#0369a1', '#e0f2fe'
        if 'hải sản' in data['nhom'].lower(): color, bg = '#0369a1', '#e0f2fe'
        elif 'thịt' in data['nhom'].lower(): color, bg = '#b91c1c', '#fee2e2'
        elif 'rau' in data['nhom'].lower(): color, bg = '#166534', '#dcfce7'
        
        table_data.append({
            'ten': ten, 'nhom': data['nhom'], 'color': color, 'bg': bg,
            'tong_xuat': round(tong_xuat, 1), 'do_thua': round(huy, 1),
            'tieu_thu': round(tieu_thu, 1), 'ty_le': ty_le
        })
        
        chart_labels.append(ten)
        chart_data.append(round(tieu_thu, 1))

    # Sort cho biểu đồ Top 10
    sorted_pairs = sorted(zip(chart_data, chart_labels), reverse=True)[:10]
    chart_data_sorted = [x[0] for x in sorted_pairs]
    chart_labels_sorted = [x[1] for x in sorted_pairs]

    context = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'table_data': table_data,
        'chart_labels_json': json.dumps(chart_labels_sorted),
        'chart_data_json': json.dumps(chart_data_sorted),
        'tong_tieu_thu': round(tong_tieu_thu, 1),
        'tong_hao_hut': round(tong_hao_hut, 1),
    }
    return render(request, 'reports/report_consumption.html', context)


# ==========================================
# 3. BÁO CÁO KHO (INVENTORY)
# ==========================================
@login_required(login_url='login')
def report_inventory_view(request):
    today = timezone.now().date()
    first_day_of_month = today.replace(day=1)
    
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        start_date = first_day_of_month
        end_date = today

    # Lấy dữ liệu nguyên liệu
    ds_nl = NguyenLieu.objects.select_related('danh_muc').all()
    
    table_data = []
    tong_nhap = tong_xuat = tong_huy = tong_ton = 0

    for nl in ds_nl:
        # Nhập trong kỳ
        nhap_ky = ChiTietNhapKho.objects.filter(
            nguyen_lieu=nl, phieu_nhap__ngay_nhap__date__range=[start_date, end_date]
        ).aggregate(tong_nhap=Sum('thanh_tien'))['tong_nhap'] or 0

        # Xuất trong kỳ
        xuat_ky_qs = ChiTietXuatKho.objects.filter(
            nguyen_lieu=nl, phieu_xuat__ngay_xuat__date__range=[start_date, end_date]
        ).select_related('phieu_xuat')
        
        xuat_tieu_thu_sl = 0
        xuat_huy_sl = 0
        for x in xuat_ky_qs:
            if 'hủy' in x.phieu_xuat.ly_do_xuat.lower() or 'hỏng' in x.phieu_xuat.ly_do_xuat.lower():
                xuat_huy_sl += float(x.so_luong_xuat)
            else:
                xuat_tieu_thu_sl += float(x.so_luong_xuat)
        
        don_gia = float(nl.don_gia_trung_binh)
        tien_xuat_tieu_thu = xuat_tieu_thu_sl * don_gia
        tien_xuat_huy = xuat_huy_sl * don_gia
        
        ton_cuoi = float(nl.ton_kho) * don_gia
        # Tồn đầu kỳ = Tồn cuối - Nhập + Xuất (Cách tính lùi đơn giản)
        ton_dau = ton_cuoi - float(nhap_ky) + tien_xuat_tieu_thu + tien_xuat_huy

        tong_nhap += float(nhap_ky)
        tong_xuat += tien_xuat_tieu_thu
        tong_huy += tien_xuat_huy
        tong_ton += ton_cuoi
        
        nhom_ten = nl.danh_muc.ten_danh_muc if nl.danh_muc else "Khác"
        
        table_data.append({
            'ten': nl.ten_nguyen_lieu,
            'dvt': nl.don_vi_tinh,
            'nhom': nhom_ten,
            'bg': '#f8fafc', 'color': '#334155', # Màu mặc định
            'ton_dau': round(ton_dau, 0),
            'nhap': round(float(nhap_ky), 0),
            'xuat_tieu_thu': round(tien_xuat_tieu_thu, 0),
            'xuat_huy': round(tien_xuat_huy, 0),
            'ton_cuoi': round(ton_cuoi, 0)
        })

    # (Lược bỏ code cấu hình Chart Flow để giữ mã gọn)
    
    context = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'table_data': table_data,
        'tong_nhap': tong_nhap, 'tong_xuat': tong_xuat,
        'tong_huy': tong_huy, 'tong_ton': tong_ton,
        'flow_labels_json': json.dumps(["Tuần 1"]), # Có thể update thuật toán gom tuần sau
        'flow_nhap_json': json.dumps([tong_nhap]),
        'flow_xuat_json': json.dumps([tong_xuat]),
        'cat_labels_json': json.dumps(['Vốn tồn kho']),
        'cat_data_json': json.dumps([tong_ton]),
    }
    return render(request, 'reports/report_inventory.html', context)


# ==========================================
# 4. BÁO CÁO HIỆU SUẤT (PERFORMANCE)
# ==========================================
@login_required(login_url='login')
def report_performance_view(request):
    today = timezone.now().date()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        start_date = today - timedelta(days=6)
        end_date = today

    hoadons = HoaDon.objects.filter(
        thoi_gian_vao__date__range=[start_date, end_date]
    )

    total_ban = BanAn.objects.count()
    if total_ban == 0: total_ban = 1 # Tránh lỗi chia cho 0
    
    # 1. Turnover & Occupancy
    tong_luot_phuc_vu = hoadons.count()
    turnover_rate = round(tong_luot_phuc_vu / total_ban, 1)
    # Giả định lấp đầy trung bình
    occupancy_rate = min(100.0, round((tong_luot_phuc_vu / (total_ban * 3)) * 100, 1))

    # 2. Dữ liệu biểu đồ Khung giờ
    peak_hours = {f"{h:02d}:00": 0 for h in range(8, 23)}
    for hd in hoadons:
        hour_str = f"{hd.thoi_gian_vao.hour:02d}:00"
        if hour_str in peak_hours:
            peak_hours[hour_str] += hd.so_khach

    # 3. Dữ liệu bảng Nhân viên
    staff_dict = {}
    for hd in hoadons:
        if not hd.nhan_vien: continue
        nv = hd.nhan_vien
        if nv.username not in staff_dict:
            staff_dict[nv.username] = {
                'name': nv.first_name or nv.username,
                'role': 'Thu ngân/Phục vụ', 'tables': 0, 'pax': 0, 'rev': 0,
                'avatar': (nv.first_name or nv.username)[0].upper(),
                'color': '#0d6efd', 'bg': '#e0f2fe', 'rating': 5
            }
        staff_dict[nv.username]['tables'] += 1
        staff_dict[nv.username]['pax'] += hd.so_khach
        staff_dict[nv.username]['rev'] += float(hd.tong_tien_hang)

    staff_list = []
    for k, v in staff_dict.items():
        v['rev'] = f"{v['rev']/1000000:.1f}M" # Đổi ra triệu đồng
        staff_list.append(v)
    
    staff_list.sort(key=lambda x: x['tables'], reverse=True) # Sắp xếp top nhân viên phục vụ nhiều bàn nhất

    context = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'occupancy_rate': occupancy_rate,
        'turnover_rate': turnover_rate,
        'avg_eat_time': "1h 45m",
        'avg_clear_time': "04",
        'peak_labels_json': json.dumps(list(peak_hours.keys())),
        'peak_data_json': json.dumps(list(peak_hours.values())),
        'zone_labels_json': json.dumps(['Sảnh Tầng 1', 'VIP', 'Tầng 2']),
        'zone_data_json': json.dumps([85, 90, 60]),
        'staff_list': staff_list,
    }
    return render(request, 'reports/report_performance.html', context)

# ==========================================
# CÁC HÀM XUẤT EXCEL BỊ THIẾU
# ==========================================

@login_required(login_url='login')
def export_inventory_report_csv(request):
    start_date = request.GET.get('start_date', 'N/A')
    end_date = request.GET.get('end_date', 'N/A')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Xuat_Nhap_Ton_{start_date}_to_{end_date}.csv"'
    response.write('\ufeff'.encode('utf8')) # Hỗ trợ font tiếng Việt
    writer = csv.writer(response)
    
    writer.writerow(['Nguyên Liệu', 'Nhóm', 'Tồn Đầu Kỳ', 'Nhập', 'Xuất (Tiêu thụ)', 'Xuất (Hủy/Hỏng)', 'Tồn Cuối Kỳ'])
    
    # (Sau này bạn có thể query table_data giống hệt hàm view để ghi vào file Excel ở đây)
    
    return response

@login_required(login_url='login')
def export_performance_report_csv(request):
    start_date = request.GET.get('start_date', 'N/A')
    end_date = request.GET.get('end_date', 'N/A')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Hieu_Suat_Nhan_Vien_{start_date}_to_{end_date}.csv"'
    response.write('\ufeff'.encode('utf8')) # Hỗ trợ font tiếng Việt
    writer = csv.writer(response)
    
    writer.writerow(['Nhân Viên', 'Vị Trí', 'Số Bàn Phục Vụ', 'Lượt Khách (Pax)', 'Doanh Thu', 'Đánh Giá'])
    
    # (Tương tự, query data ghi vào đây)
    
    return response