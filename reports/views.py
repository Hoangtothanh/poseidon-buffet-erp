from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta, datetime
from django.db import models
from django.db.models import Sum, Count, F, Avg
import json
import csv
from django.http import HttpResponse

# Nhập Models thật từ các App (Điều chỉnh tên App nếu của bạn khác nhé)
from pos.models import HoaDon, ChiTietHoaDon
from inventory.models import NguyenLieu, PhieuKho, ChiTietPhieuKho
from reception.models import BanAn
from django.contrib.auth.models import User

from core.decorators import check_quyen

# ==========================================
# 1. BÁO CÁO DOANH THU (REVENUE)
# ==========================================
@login_required(login_url='login')
@check_quyen('report_view')
def revenue_report_view(request):
    today = timezone.now().date()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Xử lý ngày tháng bộ lọc
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
    
    # Duyệt qua từng ngày trong kỳ báo cáo để tạo số liệu
    for i in range(delta_days):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime('%d/%m')
        
        # Lọc hóa đơn hợp lệ trong ngày (loại trừ hóa đơn hủy)
        hoadons = HoaDon.objects.filter(
            trang_thai='da_thanh_toan',
            thoi_gian_vao__date=current_date
        ).exclude(trang_thai='da_huy')
        
        # Tính toán Doanh thu, số HĐ của ngày
        so_hd = hoadons.count()
        doanh_thu_ngay = hoadons.aggregate(tong_tien=Sum('khach_can_tra'))['tong_tien'] or 0
        
        # Bóc tách tiền Vé Buffet và Phụ thu/Đồ uống từ ChiTietHoaDon
        chitiet_hd = ChiTietHoaDon.objects.filter(hoa_don__in=hoadons)
        
        # Tìm các mặt hàng là vé buffet (bằng cách kiểm tra trường goi_buffet hoặc tên món)
        ve_buffet = chitiet_hd.filter(
            models.Q(thuc_don__loai_mon='goi_buffet') | 
            models.Q(ten_mon_luu_tru__icontains='vé') | 
            models.Q(ten_mon_luu_tru__icontains='buffet')
        )
        
        # Số khách thực tế = Tổng số lượng vé buffet bán ra
        so_khach_ngay = ve_buffet.aggregate(tong_sl=Sum('so_luong'))['tong_sl'] or 0
        tien_ve_ngay = ve_buffet.aggregate(tong_tien_ve=Sum('thanh_tien'))['tong_tien_ve'] or 0
        
        # Tiền phụ thu = Tổng doanh thu hóa đơn - Tiền vé buffet
        tien_phu_thu_ngay = doanh_thu_ngay - tien_ve_ngay
        
        # Chuẩn bị dữ liệu vẽ Biểu đồ đường
        chart_labels.append(date_str)
        chart_data.append(float(doanh_thu_ngay))
        
        # Đổ dữ liệu vào bảng (insert(0) để ngày mới nhất nằm trên cùng)
        table_data.insert(0, { 
            'ngay': current_date.strftime('%d/%m/%Y'),
            'so_hd': so_hd, 
            'so_khach': so_khach_ngay,
            'tien_ve': float(tien_ve_ngay), 
            'tien_phu_thu': float(tien_phu_thu_ngay),
            'tong_doanh_thu': float(doanh_thu_ngay)
        })
        
        # Cộng dồn KPI tổng
        tong_doanh_thu += doanh_thu_ngay
        tong_khach += so_khach_ngay
        tong_ve += tien_ve_ngay
        tong_phu_thu += tien_phu_thu_ngay
        so_hd_tong += so_hd
        
    arpu = tong_doanh_thu / tong_khach if tong_khach > 0 else 0
    phan_tram_ve = round((float(tong_ve) / float(tong_doanh_thu)) * 100, 1) if tong_doanh_thu > 0 else 0

    context = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'tong_doanh_thu': float(tong_doanh_thu),
        'tong_khach': tong_khach,
        'arpu': float(arpu),
        'tong_ve': float(tong_ve), 
        'tong_phu_thu': float(tong_phu_thu), 
        'phan_tram_ve': phan_tram_ve,
        'so_hd_tong': so_hd_tong,
        'table_data': table_data,
        'chart_labels_json': json.dumps(chart_labels),
        'chart_data_json': json.dumps(chart_data),
    }
    return render(request, 'reports/report_revenue.html', context)

@login_required(login_url='login')
@check_quyen('report_view')
def export_revenue_csv(request):
    """ Xuất báo cáo doanh thu ra file CSV """
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    today = timezone.now().date()

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - timedelta(days=6)
            end_date = today
    else:
        start_date = today - timedelta(days=6)
        end_date = today

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Bao_Cao_Doanh_Thu_{start_date}_to_{end_date}.csv"'
    response.write('\ufeff'.encode('utf8'))  # BOM để Excel đọc tiếng Việt
    writer = csv.writer(response)

    writer.writerow(['Ngày', 'Số Hóa Đơn', 'Số Khách', 'Tiền Vé Buffet (VNĐ)', 'Phụ thu/Đồ uống (VNĐ)', 'Tổng Doanh Thu (VNĐ)'])

    delta_days = (end_date - start_date).days + 1
    tong_dt = 0
    tong_hd = 0

    for i in range(delta_days):
        current_date = start_date + timedelta(days=i)
        hoadons = HoaDon.objects.filter(
            trang_thai='da_thanh_toan',
            thoi_gian_vao__date=current_date
        )
        so_hd = hoadons.count()
        doanh_thu_ngay = hoadons.aggregate(tong=Sum('khach_can_tra'))['tong'] or 0

        chitiet = ChiTietHoaDon.objects.filter(hoa_don__in=hoadons)
        ve_buffet = chitiet.filter(
            models.Q(thuc_don__loai_mon='goi_buffet') |
            models.Q(ten_mon_luu_tru__icontains='vé') |
            models.Q(ten_mon_luu_tru__icontains='buffet')
        )
        so_khach = ve_buffet.aggregate(tong=Sum('so_luong'))['tong'] or 0
        tien_ve = ve_buffet.aggregate(tong=Sum('thanh_tien'))['tong'] or 0
        tien_phu_thu = float(doanh_thu_ngay) - float(tien_ve)

        writer.writerow([
            current_date.strftime('%d/%m/%Y'),
            so_hd,
            so_khach,
            f"{float(tien_ve):,.0f}",
            f"{tien_phu_thu:,.0f}",
            f"{float(doanh_thu_ngay):,.0f}"
        ])
        tong_dt += float(doanh_thu_ngay)
        tong_hd += so_hd

    # Dòng tổng cộng
    writer.writerow([])
    writer.writerow(['TỔNG CỘNG', tong_hd, '', '', '', f"{tong_dt:,.0f}"])

    return response


# ==========================================
# 2. BÁO CÁO TIÊU THỤ (CONSUMPTION)
# ==========================================
@login_required(login_url='login')
@check_quyen('report_view')
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
    chi_tiet_xuats = ChiTietPhieuKho.objects.filter(
        phieu__loai_phieu='xuat',
        phieu__ngay_thuc_hien__date__range=[start_date, end_date]
    ).select_related('nguyen_lieu', 'phieu')

    mon_stats = {}
    tong_tieu_thu = tong_hao_hut = 0

    for ct in chi_tiet_xuats:
        ten_nl = ct.nguyen_lieu.ten_nguyen_lieu
        nhom_nl = ct.nguyen_lieu.get_danh_muc_display() if ct.nguyen_lieu.danh_muc else "Khác"
        sl = float(ct.so_luong)
        
        if ten_nl not in mon_stats:
            mon_stats[ten_nl] = {'nhom': nhom_nl, 'xuat_bep': 0, 'xuat_huy': 0}
        
        # Kiểm tra lý do xuất
        ly_do = ct.phieu.ghi_chu.lower() if ct.phieu.ghi_chu else ""
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


@login_required(login_url='login')
@check_quyen('report_view')
def export_consumption_csv(request):
    """ Xuất dữ liệu báo cáo Tiêu thụ nguyên liệu ra file CSV """
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    today = timezone.now().date()

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - timedelta(days=6)
            end_date = today
    else:
        start_date = today - timedelta(days=6)
        end_date = today

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Bao_Cao_Tieu_Thu_{start_date}_{end_date}.csv"'
    response.write('\ufeff'.encode('utf8'))  # BOM để Excel đọc được tiếng Việt

    writer = csv.writer(response)
    writer.writerow(['Tên Nguyên Liệu', 'Nhóm', 'Tổng Xuất (Line)', 'Đồ Thừa (Hủy)', 'Tiêu Thụ Thực', 'Tỷ Lệ Tiêu Thụ (%)'])

    chi_tiet_xuats = ChiTietPhieuKho.objects.filter(
        phieu__loai_phieu='xuat',
        phieu__ngay_thuc_hien__date__range=[start_date, end_date]
    ).select_related('nguyen_lieu', 'phieu')

    mon_stats = {}
    for ct in chi_tiet_xuats:
        ten_nl = ct.nguyen_lieu.ten_nguyen_lieu
        nhom_nl = ct.nguyen_lieu.get_danh_muc_display() if ct.nguyen_lieu.danh_muc else 'Khác'
        sl = float(ct.so_luong)
        if ten_nl not in mon_stats:
            mon_stats[ten_nl] = {'nhom': nhom_nl, 'xuat_bep': 0, 'xuat_huy': 0}
        ly_do = ct.phieu.ghi_chu.lower() if ct.phieu.ghi_chu else ''
        if 'hủy' in ly_do or 'hỏng' in ly_do:
            mon_stats[ten_nl]['xuat_huy'] += sl
        else:
            mon_stats[ten_nl]['xuat_bep'] += sl

    for ten, data in sorted(mon_stats.items()):
        tong_xuat = data['xuat_bep'] + data['xuat_huy']
        tieu_thu = data['xuat_bep']
        huy = data['xuat_huy']
        ty_le = round((tieu_thu / tong_xuat) * 100, 1) if tong_xuat > 0 else 0
        writer.writerow([ten, data['nhom'], round(tong_xuat, 2), round(huy, 2), round(tieu_thu, 2), ty_le])

    return response


# ==========================================
# 3. BÁO CÁO KHO (INVENTORY)
# ==========================================
@login_required(login_url='login')
@check_quyen('report_view')
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
    ds_nl = NguyenLieu.objects.all()
    
    table_data = []
    tong_nhap = tong_xuat = tong_huy = tong_ton = 0

    for nl in ds_nl:
        # Nhập trong kỳ
        nhap_ky = ChiTietPhieuKho.objects.filter(
            nguyen_lieu=nl, phieu__loai_phieu='nhap', phieu__ngay_thuc_hien__date__range=[start_date, end_date]
        ).aggregate(tong_nhap=Sum('thanh_tien'))['tong_nhap'] or 0

        # Xuất trong kỳ
        xuat_ky_qs = ChiTietPhieuKho.objects.filter(
            nguyen_lieu=nl, phieu__loai_phieu='xuat', phieu__ngay_thuc_hien__date__range=[start_date, end_date]
        ).select_related('phieu')
        
        xuat_tieu_thu_sl = 0
        xuat_huy_sl = 0
        for x in xuat_ky_qs:
            ly_do_lower = x.phieu.ghi_chu.lower() if x.phieu.ghi_chu else ""
            if 'hủy' in ly_do_lower or 'hỏng' in ly_do_lower:
                xuat_huy_sl += float(x.so_luong)
            else:
                xuat_tieu_thu_sl += float(x.so_luong)
        
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
        
        nhom_ten = nl.get_danh_muc_display() if nl.danh_muc else "Khác"
        
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

    # ========================================================
    # TÍNH TOÁN DỮ LIỆU BIỂU ĐỒ FLOW NHẬP/XUẤT THEO TUẦN THỰC
    # ========================================================
    from math import ceil
    delta_days = (end_date - start_date).days + 1
    # Gom theo tuần (tối đa 8 tuần)
    so_tuan = max(1, ceil(delta_days / 7))
    flow_labels = []
    flow_nhap_list = []
    flow_xuat_list = []

    for w in range(so_tuan):
        w_start = start_date + timedelta(days=w * 7)
        w_end = min(w_start + timedelta(days=6), end_date)
        label = f"Tuần {w + 1} ({w_start.strftime('%d/%m')})"
        flow_labels.append(label)

        nhap_tuan = ChiTietPhieuKho.objects.filter(
            phieu__loai_phieu='nhap',
            phieu__ngay_thuc_hien__date__range=[w_start, w_end]
        ).aggregate(tong=Sum('thanh_tien'))['tong'] or 0

        xuat_tuan = 0
        xuat_ky = ChiTietPhieuKho.objects.filter(
            phieu__loai_phieu='xuat',
            phieu__ngay_thuc_hien__date__range=[w_start, w_end]
        ).select_related('nguyen_lieu')
        for x in xuat_ky:
            xuat_tuan += float(x.so_luong) * float(x.nguyen_lieu.don_gia_trung_binh)

        flow_nhap_list.append(round(float(nhap_tuan), 0))
        flow_xuat_list.append(round(xuat_tuan, 0))

    # ========================================================
    # TÍNH TOÁN DỮ LIỆU BIỂU ĐỒ TRÒN PHÂN LOẠI THEO DANH MỤC
    # ========================================================
    cat_labels = []
    cat_data = []
    
    for dm_val, dm_label in NguyenLieu.DANH_MUC_CHOICES:
        ton_dm = NguyenLieu.objects.filter(danh_muc=dm_val).aggregate(
            tong=Sum(models.F('ton_kho') * models.F('don_gia_trung_binh'),
                     output_field=models.FloatField())
        )['tong'] or 0
        if ton_dm > 0:
            cat_labels.append(dm_label)
            cat_data.append(round(float(ton_dm), 0))

    # Fallback nếu chưa có danh mục
    if not cat_labels:
        cat_labels = ['Tổng tồn kho']
        cat_data = [tong_ton]

    context = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'table_data': table_data,
        'tong_nhap': tong_nhap, 'tong_xuat': tong_xuat,
        'tong_huy': tong_huy, 'tong_ton': tong_ton,
        'flow_labels_json': json.dumps(flow_labels),
        'flow_nhap_json': json.dumps(flow_nhap_list),
        'flow_xuat_json': json.dumps(flow_xuat_list),
        'cat_labels_json': json.dumps(cat_labels),
        'cat_data_json': json.dumps(cat_data),
    }
    return render(request, 'reports/report_inventory.html', context)


# ==========================================
# 4. BÁO CÁO HIỆU SUẤT (PERFORMANCE)
# ==========================================
@login_required(login_url='login')
@check_quyen('report_view')
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
@check_quyen('report_view')
def export_inventory_report_csv(request):
    """ Xuất báo cáo xuất nhập tồn kho ra file CSV """
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    today = timezone.now().date()
    first_day = today.replace(day=1)

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = first_day
            end_date = today
    else:
        start_date = first_day
        end_date = today

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Xuat_Nhap_Ton_{start_date}_to_{end_date}.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)

    writer.writerow([
        'Nguyên Liệu', 'Nhóm', 'ĐVT',
        'Tồn Đầu Kỳ (VNĐ)', 'Nhập Kỳ (VNĐ)',
        'Xuất Tiêu Thụ (VNĐ)', 'Xuất Hủy/Hỏng (VNĐ)', 'Tồn Cuối Kỳ (VNĐ)'
    ])

    from inventory.models import NguyenLieu, ChiTietPhieuKho
    ds_nl = NguyenLieu.objects.all()

    for nl in ds_nl:
        nhap_ky = ChiTietPhieuKho.objects.filter(
            nguyen_lieu=nl,
            phieu__loai_phieu='nhap',
            phieu__ngay_thuc_hien__date__range=[start_date, end_date]
        ).aggregate(tong=Sum('thanh_tien'))['tong'] or 0

        xuat_ky_qs = ChiTietPhieuKho.objects.filter(
            nguyen_lieu=nl,
            phieu__loai_phieu='xuat',
            phieu__ngay_thuc_hien__date__range=[start_date, end_date]
        ).select_related('phieu')

        xuat_tieu_thu_sl = 0
        xuat_huy_sl = 0
        for x in xuat_ky_qs:
            ly_do_lower = x.phieu.ghi_chu.lower() if x.phieu.ghi_chu else ""
            if 'hủy' in ly_do_lower or 'hỏng' in ly_do_lower:
                xuat_huy_sl += float(x.so_luong)
            else:
                xuat_tieu_thu_sl += float(x.so_luong)

        don_gia = float(nl.don_gia_trung_binh)
        tien_xuat_tt = xuat_tieu_thu_sl * don_gia
        tien_xuat_huy = xuat_huy_sl * don_gia
        ton_cuoi = float(nl.ton_kho) * don_gia
        ton_dau = ton_cuoi - float(nhap_ky) + tien_xuat_tt + tien_xuat_huy

        nhom = nl.get_danh_muc_display() if nl.danh_muc else 'Khác'
        writer.writerow([
            nl.ten_nguyen_lieu, nhom, nl.don_vi_tinh,
            f"{ton_dau:,.0f}", f"{float(nhap_ky):,.0f}",
            f"{tien_xuat_tt:,.0f}", f"{tien_xuat_huy:,.0f}", f"{ton_cuoi:,.0f}"
        ])

    return response

@login_required(login_url='login')
@check_quyen('report_view')
def export_performance_report_csv(request):
    """ Xuất báo cáo hiệu suất nhân viên ra file CSV """
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    today = timezone.now().date()

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - timedelta(days=6)
            end_date = today
    else:
        start_date = today - timedelta(days=6)
        end_date = today

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Hieu_Suat_Nhan_Vien_{start_date}_to_{end_date}.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response)

    writer.writerow(['Nhân Viên', 'Tài Khoản', 'Số Bàn Phục Vụ', 'Lượt Khách (Pax)', 'Doanh Thu (VNĐ)'])

    hoadons = HoaDon.objects.filter(
        thoi_gian_vao__date__range=[start_date, end_date]
    ).exclude(trang_thai='da_huy')

    staff_dict = {}
    for hd in hoadons:
        if not hd.nhan_vien:
            continue
        nv = hd.nhan_vien
        uid = nv.id
        if uid not in staff_dict:
            staff_dict[uid] = {
                'ten': f"{nv.last_name} {nv.first_name}".strip() or nv.username,
                'username': nv.username,
                'tables': 0,
                'pax': 0,
                'rev': 0.0
            }
        staff_dict[uid]['tables'] += 1
        staff_dict[uid]['pax'] += hd.so_khach
        staff_dict[uid]['rev'] += float(hd.tong_tien_hang)

    staff_list = sorted(staff_dict.values(), key=lambda x: x['rev'], reverse=True)

    for s in staff_list:
        writer.writerow([
            s['ten'], s['username'],
            s['tables'], s['pax'],
            f"{s['rev']:,.0f}"
        ])

    if not staff_list:
        writer.writerow(['Không có dữ liệu trong khoảng thời gian này.'])

    return response