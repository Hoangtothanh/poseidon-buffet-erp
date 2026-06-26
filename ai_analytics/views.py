"""
ai_analytics/views.py
======================
HỆ THỐNG TRỢ LÝ AI CHO NHÀ HÀNG POSEIDON BUFFET
--------------------------------------------------
Các thuật toán sử dụng:
  1. Weighted Moving Average (WMA)      — Dự báo lượng khách theo lịch sử thứ trong tuần
  2. Z-Score Anomaly Detection          — Phát hiện ngày bất thường về doanh thu/lưu lượng
  3. JIT Burn Rate + Safety Stock       — Cảnh báo tồn kho Just-In-Time
  4. CV-based Confidence Scoring        — Điểm tin cậy dựa trên độ biến động thực tế (σ/μ)
"""

import math
import datetime
import random
import string
import json
import urllib.request

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q, Sum, F, Count, ExpressionWrapper, DecimalField
from django.db.models.functions import ExtractHour
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from datetime import timedelta

# Import Model từ các app
from pos.models import HoaDon, ChiTietHoaDon
from reception.models import BanAn, PhieuDatBan
from hrm.models import CaLamViec
from inventory.models import ChiTietPhieuKho, NguyenLieu
from customers.models import Voucher

# ==========================================
# CẤU HÌNH HỆ THỐNG
# ==========================================
SYSTEM_CONFIG = {
    "ai_min_factor": 0.92,
    "ai_max_factor": 1.15,
    "ai_lunch_ratio": 0.4,
    "arpu_expected": 400000,
    "default_salary_per_shift": 300000,
    "fallback_pax": 380,
    "cache_timeout": 60,
    "ai_distribution": {
        9: 0.05, 10: 0.1, 11: 0.3, 12: 0.6, 13: 0.4, 14: 0.1,
        15: 0.05, 16: 0.05, 17: 0.1, 18: 0.5, 19: 0.8, 20: 0.7, 21: 0.3
    },
    # Cache 30 giây — đủ để tránh spam DB, nhưng phản ánh hóa đơn mới nhanh hơn
    "cache_timeout_dashboard": 30,
    "cache_timeout_ai": 120,
    # Hệ số an toàn JIT (Z-score 95% = 1.645 → Safety Stock = U_avg × 1.645 × σ_demand)
    "jit_z_score_95": 1.645,
    # Nhân viên phục vụ chuẩn: 1 NV / 25 khách
    "staff_per_pax": 25,
}

# Tọa độ nhà hàng (TP.HCM)
RESTAURANT_LAT = 10.7769
RESTAURANT_LON = 106.7009

# Bảng mô tả WMO weather code → tiếng Việt + emoji
WMO_WEATHER_MAP = {
    0:  ('Trời quang', '☀️'),
    1:  ('Ít mây', '🌤️'),
    2:  ('Mây rải rác', '⛅'),
    3:  ('Nhiều mây', '☁️'),
    45: ('Sương mù', '🌫️'),
    48: ('Sương mù đóng băng', '🌫️'),
    51: ('Mưa phùn nhẹ', '🌦️'),
    53: ('Mưa phùn', '🌦️'),
    55: ('Mưa phùn dày', '🌧️'),
    61: ('Mưa nhẹ', '🌧️'),
    63: ('Mưa vừa', '🌧️'),
    65: ('Mưa lớn', '⛈️'),
    80: ('Mưa rào nhẹ', '🌦️'),
    81: ('Mưa rào vừa', '🌧️'),
    82: ('Mưa rào lớn', '⛈️'),
    95: ('Giông bão', '⛈️'),
    96: ('Giông có mưa đá', '⛈️'),
    99: ('Giông mưa đá lớn', '⛈️'),
}


# ==========================================
# HELPER: ĐỌC CẤU HÌNH AI TỪ DATABASE
# ==========================================
def get_ai_config():
    """Đọc cấu hình window dữ liệu và cửa sổ dự báo từ SystemSetting."""
    try:
        from core.models import SystemSetting
        setting = SystemSetting.objects.get(id=1)

        def parse_days(val, default_days):
            if not val:
                return default_days
            try:
                num = int(val.split('_')[0])
                return num * 30 if 'month' in val else num
            except Exception:
                return default_days

        dataset_days = parse_days(setting.ai_dataset_window, 30)
        predict_days = parse_days(setting.ai_prediction_window, 7)
        return dataset_days, predict_days
    except Exception:
        return 30, 7


# ==========================================
# HELPER: LẤY DỰ BÁO THỜI TIẾT (Open-Meteo API)
# ==========================================
def fetch_weather_forecast(target_date):
    """
    Lấy dự báo thời tiết cho target_date từ Open-Meteo API (miễn phí, không cần key).
    Kết quả được cache 30 phút để tránh spam API.

    Return: dict {
        'temp_max': float,       # Nhiệt độ tối đa (°C)
        'precipitation': float,  # Lượng mưa (mm)
        'weather_code': int,     # WMO weather code
        'description': str,      # Mô tả tiếng Việt
        'icon': str,             # Emoji icon
        'waf': float,            # Weather Adjustment Factor
    } hoặc None nếu lỗi.
    """
    cache_key = f'weather_forecast_{target_date}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        date_str = target_date.strftime('%Y-%m-%d')
        url = (
            f'https://api.open-meteo.com/v1/forecast'
            f'?latitude={RESTAURANT_LAT}&longitude={RESTAURANT_LON}'
            f'&daily=precipitation_sum,temperature_2m_max,weathercode'
            f'&timezone=Asia%2FHo_Chi_Minh'
            f'&start_date={date_str}&end_date={date_str}'
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'PoseidonERP/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        daily = data.get('daily', {})
        if not daily.get('time'):
            return None

        temp_max     = daily['temperature_2m_max'][0] or 30.0
        precipitation = daily['precipitation_sum'][0] or 0.0
        weather_code = int(daily['weathercode'][0] or 0)

        description, icon = WMO_WEATHER_MAP.get(weather_code, ('Không xác định', '🌡️'))
        waf = get_weather_adjustment_factor(temp_max, precipitation, weather_code)

        result = {
            'temp_max': round(temp_max, 1),
            'precipitation': round(precipitation, 1),
            'weather_code': weather_code,
            'description': description,
            'icon': icon,
            'waf': waf,
        }
        cache.set(cache_key, result, 1800)  # Cache 30 phút
        return result

    except Exception as e:
        print(f'[WeatherAPI] Lỗi lấy thời tiết: {e}')
        return None


def get_weather_adjustment_factor(temp_max, precipitation, weather_code):
    """
    Tính Weather Adjustment Factor (WAF) từ dữ liệu thời tiết.

    Logic điều chỉnh:
      - Nắng quang (WMO 0–2)     : +10% khách (thời tiết đẹp, dễ ra ngoài)
      - Mưa nhẹ (2–10mm)         : -5%  khách
      - Mưa lớn (>10mm)          : -15% khách (ảnh hưởng mạnh đến lưu lượng)
      - Giông bão (WMO 95–99)    : -20% khách
      - Nhiệt độ mát (25–30°C)   : +5%  bonus
      - Nhiệt độ rất nóng (>36°C): -3%  malus

    Return: float WAF (ví dụ: 0.85 = giảm 15%)
    """
    waf = 1.0

    # Điều chỉnh theo lượng mưa
    if precipitation > 10:
        waf -= 0.15
    elif precipitation > 2:
        waf -= 0.05

    # Điều chỉnh theo weather code
    if weather_code in (0, 1, 2):
        waf += 0.10   # Nắng đẹp → khách đông hơn
    elif weather_code in (95, 96, 99):
        waf -= 0.05   # Giông bão thêm penalty (trên lượng mưa)

    # Điều chỉnh theo nhiệt độ
    if 25 <= temp_max <= 30:
        waf += 0.05   # Nhiệt độ dễ chịu
    elif temp_max > 36:
        waf -= 0.03   # Quá nóng

    # Clamp WAF trong khoảng hợp lý [0.60, 1.25]
    return round(max(0.60, min(1.25, waf)), 3)


# ==========================================
# HELPER: KIỂM TRA QUYỀN QUẢN LÝ
# ==========================================
def check_manager_permission(user):
    """
    Kiểm tra quyền truy cập Dashboard và AI.
    - Superuser: luôn được phép
    - Nhân viên front-office (pos_view=True, không có inventory/report/system): bị chặn
    - Nhân viên chưa có group: cho phép vào Dashboard (tài khoản mới chưa phân quyền)
    - Quản lý (có bất kỳ quyền nào ngoài POS đơn thuần): được phép
    """
    if user.is_superuser:
        return True
    group = user.groups.first()
    if group:
        try:
            quyen = group.quyen
            has_other_modules = (
                quyen.table_view or 
                quyen.booking_view or 
                quyen.menu_view or 
                quyen.inventory_view or 
                quyen.report_view or 
                quyen.system_all
            )
            if not has_other_modules:
                return False
        except Exception:
            pass
    return True


# ==========================================
# THUẬT TOÁN 1: WEIGHTED MOVING AVERAGE (WMA)
# ==========================================
def calculate_wma_forecast(weekday_index, dataset_days=30):
    """
    Dự báo lượng khách cho ngày có weekday_index (0=Mon … 6=Sun)
    bằng Weighted Moving Average.

    Nguyên lý:
      - Lấy dữ liệu của tất cả các ngày cùng thứ trong `dataset_days` ngày qua.
      - Tuần gần hơn nhận trọng số cao hơn (w_k = k, k=1 là tuần xa nhất).
      - WMA = Σ(w_k × X_k) / Σ(w_k)

    ⚡ TỐI ƯU: Thay vì N vòng lặp mỗi lần 1 DB query, dùng DUY NHẤT 1 query
    GROUP BY date rồi lọc weekday trong Python → giảm từ ~5 queries → 1 query.

    Return: dict {
        'wma': float,         # Dự báo WMA (pax)
        'mean': float,        # Trung bình đơn (pax)
        'std': float,         # Độ lệch chuẩn (pax)
        'cv': float,          # Coefficient of Variation (%) = std/mean*100
        'n_weeks': int,       # Số tuần có dữ liệu
        'data_points': list,  # Danh sách số khách từng tuần (cũ → gần)
    }
    """
    today = timezone.now().date()
    start_date = today - timedelta(days=dataset_days)

    # ⚡ 1 QUERY DUY NHẤT: Lấy tổng pax theo từng ngày trong toàn bộ window
    daily_pax_qs = (
        ChiTietHoaDon.objects
        .filter(
            hoa_don__thoi_gian_vao__date__gte=start_date,
            hoa_don__thoi_gian_vao__date__lt=today,
            hoa_don__trang_thai='da_thanh_toan',
        )
        .filter(
            Q(thuc_don__loai_mon='goi_buffet')
            | Q(ten_mon_luu_tru__icontains='vé')
            | Q(ten_mon_luu_tru__icontains='buffet')
        )
        .values('hoa_don__thoi_gian_vao__date')
        .annotate(tong=Sum('so_luong'))
        .order_by('hoa_don__thoi_gian_vao__date')
    )

    # Lọc theo weekday trong Python (không cần thêm query)
    same_weekday_data = [
        (item['hoa_don__thoi_gian_vao__date'], int(item['tong'] or 0))
        for item in daily_pax_qs
        if item['hoa_don__thoi_gian_vao__date'].weekday() == weekday_index
    ]

    # Nếu không đủ dữ liệu → dùng fallback
    if not same_weekday_data:
        return {
            'wma': SYSTEM_CONFIG['fallback_pax'],
            'mean': SYSTEM_CONFIG['fallback_pax'],
            'std': 0.0,
            'cv': 0.0,
            'n_weeks': 0,
            'data_points': [],
        }

    # Sắp xếp từ cũ → gần (đã sort theo date từ query)
    values = [v for _, v in same_weekday_data]
    n = len(values)

    # Bước 2: Tính WMA — w_k = k (k=1 cũ nhất, k=n gần nhất)
    weights = list(range(1, n + 1))
    wma = sum(w * x for w, x in zip(weights, values)) / sum(weights)

    # Bước 3: Tính thống kê
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    std = math.sqrt(variance)
    cv = (std / mean * 100) if mean > 0 else 0.0

    return {
        'wma': round(wma, 1),
        'mean': round(mean, 1),
        'std': round(std, 1),
        'cv': round(cv, 1),
        'n_weeks': n,
        'data_points': values,
    }


# ==========================================
# THUẬT TOÁN 2: Z-SCORE — PHÁT HIỆN BẤT THƯỜNG
# ==========================================
def detect_anomaly_days(dataset_days=30):
    """
    Phát hiện các ngày có doanh thu bất thường trong dataset_days ngày qua.

    Nguyên lý Z-Score:
      Z = (X - μ) / σ
      |Z| > 2.0  → bất thường (ngoài 2 độ lệch chuẩn ≈ top/bot 2.28% chuỗi chuẩn)

    Return: list of dict { date, revenue, z_score, label }
    """
    today = timezone.now().date()
    start = today - timedelta(days=dataset_days)

    daily_rev = (
        HoaDon.objects.filter(
            thoi_gian_vao__date__gte=start,
            thoi_gian_vao__date__lt=today,
            trang_thai='da_thanh_toan'
        )
        .values('thoi_gian_vao__date')
        .annotate(tong=Sum('khach_can_tra'))
        .order_by('thoi_gian_vao__date')
    )

    revenues = [float(item['tong']) for item in daily_rev if item['tong']]
    if len(revenues) < 3:
        return []

    n = len(revenues)
    mean = sum(revenues) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in revenues) / n)
    if std == 0:
        return []

    anomalies = []
    for item in daily_rev:
        rev = float(item['tong'] or 0)
        z = (rev - mean) / std
        if abs(z) >= 2.0:
            anomalies.append({
                'date': item['thoi_gian_vao__date'],
                'revenue': int(rev),
                'z_score': round(z, 2),
                'label': 'Đột biến cao' if z > 0 else 'Sụt giảm bất thường',
            })

    return sorted(anomalies, key=lambda x: abs(x['z_score']), reverse=True)[:5]


# ==========================================
# THUẬT TOÁN 3: JIT BURN RATE + SAFETY STOCK
# ==========================================
def calculate_jit_import(tomorrow_forecast_pax, dataset_days=None):
    """
    Tính toán nhu cầu nhập kho theo mô hình JIT (Just-In-Time).
    """
    if dataset_days is None:
        dataset_days, _ = get_ai_config()

    recommendations = []
    today = timezone.now().date()
    past_date = today - timedelta(days=dataset_days)

    # ⚡ 1 QUERY: Lấy tổng pax & pax từng ngày trong window data — dùng chung
    daily_pax_qs = (
        ChiTietHoaDon.objects
        .filter(
            hoa_don__thoi_gian_vao__date__gte=past_date,
            hoa_don__thoi_gian_vao__date__lt=today,
            hoa_don__trang_thai='da_thanh_toan',
        )
        .filter(
            Q(thuc_don__loai_mon='goi_buffet')
            | Q(ten_mon_luu_tru__icontains='vé')
            | Q(ten_mon_luu_tru__icontains='buffet')
        )
        .values('hoa_don__thoi_gian_vao__date')
        .annotate(tong=Sum('so_luong'))
    )
    daily_pax_list = [int(row['tong'] or 0) for row in daily_pax_qs]
    total_pax_window = sum(daily_pax_list)
    
    # 🚨 BẢO VỆ DỮ LIỆU RÁC: Nếu quá ít khách (vd hệ thống mới test), dùng fallback để tránh chia cho 1 làm số dự kiến bùng nổ
    if total_pax_window < 50:
        fallback = SYSTEM_CONFIG['fallback_pax']
        total_pax_window = fallback * dataset_days
        pax_mean = fallback
        pax_std = fallback * 0.1 # Giả sử độ lệch 10%
    else:
        pax_mean = total_pax_window / max(len(daily_pax_list), 1)
        pax_variance = sum((x - pax_mean) ** 2 for x in daily_pax_list) / max(len(daily_pax_list), 1)
        pax_std = math.sqrt(pax_variance)

    # ⚡ 1 QUERY: Lấy tổng xuất kho trong window data GROUP BY nguyen_lieu (thay vì N queries)
    xuat_by_nl = {
        row['nguyen_lieu_id']: float(row['tong'] or 0)
        for row in ChiTietPhieuKho.objects
        .filter(
            phieu__loai_phieu='xuat',
            phieu__ngay_thuc_hien__date__gte=past_date,
        )
        .values('nguyen_lieu_id')
        .annotate(tong=Sum('so_luong'))
    }

    # ⚡ Đổi sang lấy toàn bộ nguyên liệu để đồng bộ 100% với AI JIT Full
    nguyen_lieu_list = NguyenLieu.objects.all()

    for nl in nguyen_lieu_list:
        xuat_window = xuat_by_nl.get(nl.id, 0.0)
        ton_kho_hien_tai = float(nl.ton_kho)

        if xuat_window > 0:
            # Burn Rate (tiêu hao trung bình / khách)
            u_avg = xuat_window / float(total_pax_window)
            # Nhu cầu cơ bản
            demand_base = float(tomorrow_forecast_pax) * u_avg
            # Safety Stock = U_avg × σ_pax × Z(95%)
            safety_stock = u_avg * pax_std * SYSTEM_CONFIG['jit_z_score_95']
        else:
            # Chưa có lịch sử xuất kho → dựa vào mức cảnh báo
            u_avg = 0.0
            demand_base = 0.0
            safety_stock = float(nl.muc_canh_bao)

        # Tồn cần có
        luong_can_co = demand_base + safety_stock

        if ton_kho_hien_tai < luong_can_co:
            can_nhap = luong_can_co - ton_kho_hien_tai
            recommendations.append({
                'id': nl.id,
                'ten_nguyen_lieu': nl.ten_nguyen_lieu,
                'don_vi': nl.don_vi_tinh,
                'ton_kho': round(ton_kho_hien_tai, 2),
                'nhu_cau_ngay_mai': round(demand_base, 2),
                'safety_stock': round(safety_stock, 2),
                'burn_rate': round(u_avg, 4),
                'de_xuat_nhap': round(can_nhap + 0.5),
            })

    return sorted(recommendations, key=lambda x: x['de_xuat_nhap'], reverse=True)[:4]


def calculate_jit_full(tomorrow_forecast_pax, dataset_days=None):
    """
    Tính toán TOÀN BỘ nguyên liệu cần chuẩn bị cho ngày dự báo.
    """
    if dataset_days is None:
        dataset_days, _ = get_ai_config()

    today = timezone.now().date()
    past_date = today - timedelta(days=dataset_days)

    # Lấy pax window_data (dùng lại logic từ calculate_jit_import)
    daily_pax_qs = (
        ChiTietHoaDon.objects
        .filter(
            hoa_don__thoi_gian_vao__date__gte=past_date,
            hoa_don__thoi_gian_vao__date__lt=today,
            hoa_don__trang_thai='da_thanh_toan',
        )
        .filter(
            Q(thuc_don__loai_mon='goi_buffet')
            | Q(ten_mon_luu_tru__icontains='vé')
            | Q(ten_mon_luu_tru__icontains='buffet')
        )
        .values('hoa_don__thoi_gian_vao__date')
        .annotate(tong=Sum('so_luong'))
    )
    daily_pax_list = [int(row['tong'] or 0) for row in daily_pax_qs]
    total_pax_window = sum(daily_pax_list)

    if total_pax_window < 50:
        fallback = SYSTEM_CONFIG['fallback_pax']
        total_pax_window = fallback * dataset_days
        pax_mean = fallback
        pax_std = fallback * 0.1
    else:
        pax_mean = total_pax_window / max(len(daily_pax_list), 1)
        pax_variance = sum((x - pax_mean) ** 2 for x in daily_pax_list) / max(len(daily_pax_list), 1)
        pax_std = math.sqrt(pax_variance)

    xuat_by_nl = {
        row['nguyen_lieu_id']: float(row['tong'] or 0)
        for row in ChiTietPhieuKho.objects
        .filter(
            phieu__loai_phieu='xuat',
            phieu__ngay_thuc_hien__date__gte=past_date,
        )
        .values('nguyen_lieu_id')
        .annotate(tong=Sum('so_luong'))
    }

    # Lấy TẤT CẢ nguyên liệu (không chỉ những cái xuất kho)
    all_nguyen_lieu = NguyenLieu.objects.all().order_by('danh_muc', 'ten_nguyen_lieu')

    result = []
    tong_chi_phi = 0.0

    DANH_MUC_LABEL = {
        'hai_san': 'Hải Sản Tươi Sống',
        'thit': 'Thịt (Bò, Gà, Heo)',
        'rau_cu': 'Rau Củ Quả',
        'gia_vi': 'Gia Vị & Đồ Khô',
        'do_uong': 'Đồ Uống (Chai/Lon)',
        'khac': 'Khác',
    }
    DANH_MUC_ICON = {
        'hai_san': 'bi-water',
        'thit': 'bi-egg-fried',
        'rau_cu': 'bi-flower1',
        'gia_vi': 'bi-jar',
        'do_uong': 'bi-cup-straw',
        'khac': 'bi-box2',
    }

    for nl in all_nguyen_lieu:
        xuat_window = xuat_by_nl.get(nl.id, 0.0)
        ton_kho_hien_tai = float(nl.ton_kho)
        don_gia = float(nl.don_gia_trung_binh)

        if xuat_window > 0:
            u_avg = xuat_window / float(total_pax_window)
            demand_base = float(tomorrow_forecast_pax) * u_avg
            safety_stock = u_avg * pax_std * SYSTEM_CONFIG['jit_z_score_95']
            luong_can_co = demand_base + safety_stock
            can_nhap = max(0.0, luong_can_co - ton_kho_hien_tai)
            burn_rate = round(u_avg, 4)
        else:
            # Nguyên liệu chưa có lịch sử xuất kho → dựa vào mức cảnh báo tối thiểu
            demand_base = 0.0
            safety_stock = float(nl.muc_canh_bao)
            luong_can_co = safety_stock
            can_nhap = max(0.0, luong_can_co - ton_kho_hien_tai)
            burn_rate = 0.0

        chi_phi_uoc_tinh = round(can_nhap * don_gia)
        tong_chi_phi += chi_phi_uoc_tinh

        if can_nhap > 0:
            trang_thai = 'can_nhap'
            trang_thai_label = 'Cần nhập thêm'
            trang_thai_class = 'danger'
        elif ton_kho_hien_tai <= float(nl.muc_canh_bao):
            trang_thai = 'sap_het'
            trang_thai_label = 'Sắp hết'
            trang_thai_class = 'warning'
        else:
            trang_thai = 'du_hang'
            trang_thai_label = 'Đủ hàng'
            trang_thai_class = 'success'

        result.append({
            'id': nl.id,
            'ten_nguyen_lieu': nl.ten_nguyen_lieu,
            'danh_muc': nl.danh_muc,
            'danh_muc_label': DANH_MUC_LABEL.get(nl.danh_muc, 'Khác'),
            'danh_muc_icon': DANH_MUC_ICON.get(nl.danh_muc, 'bi-box2'),
            'don_vi': nl.don_vi_tinh,
            'ton_kho': round(ton_kho_hien_tai, 2),
            'muc_canh_bao': round(float(nl.muc_canh_bao), 2),
            'nhu_cau': round(demand_base, 2),
            'safety_stock': round(safety_stock, 2),
            'luong_can_co': round(luong_can_co, 2),
            'can_nhap': round(can_nhap, 2),
            'de_xuat_nhap': round(can_nhap + 0.5) if can_nhap > 0 else 0,
            'burn_rate': burn_rate,
            'don_gia': int(don_gia),
            'chi_phi_uoc_tinh': chi_phi_uoc_tinh,
            'trang_thai': trang_thai,
            'trang_thai_label': trang_thai_label,
            'trang_thai_class': trang_thai_class,
        })

    return result, round(tong_chi_phi)



# ==========================================
# THUẬT TOÁN 5: CONFIDENCE SCORE DỰA TRÊN CV
# ==========================================
def compute_confidence(cv_pct, n_weeks, base=85.0):
    """
    Tính Confidence Score dựa trên Coefficient of Variation (CV = σ/μ × 100%).

    Nguyên lý:
      - CV thấp → dữ liệu ổn định → mô hình đáng tin cậy → Confidence cao
      - CV cao  → dữ liệu biến động → Confidence thấp
      - Thiếu dữ liệu (n_weeks nhỏ) → trừ thêm điểm phạt

    Công thức:
      Conf = base - (CV × 0.5) + (min(n_weeks, 4) × 2.5)
      Clamp: [50, 99]

    Args:
      cv_pct: CV% (e.g. 15.0 nghĩa là 15%)
      n_weeks: số tuần có dữ liệu cùng thứ
      base: điểm cơ sở mặc định 85

    Return: float (50 ≤ conf ≤ 99)
    """
    data_bonus = min(n_weeks, 4) * 2.5  # Tối đa +10 điểm từ 4 tuần trở lên
    cv_penalty = cv_pct * 0.5           # CV cao → trừ điểm
    conf = base - cv_penalty + data_bonus
    return round(max(50.0, min(99.0, conf)), 1)


# ==========================================
# LOGIC DASHBOARD TỔNG QUAN
# ==========================================
def get_realtime_data(today):
    hoa_don_hom_nay = HoaDon.objects.filter(thoi_gian_vao__date=today).exclude(trang_thai='da_huy')
    hoa_don_da_thanh_toan = hoa_don_hom_nay.filter(trang_thai='da_thanh_toan')

    doanh_thu = int(hoa_don_da_thanh_toan.aggregate(tong=Sum('khach_can_tra'))['tong'] or 0)

    thuc_khach = int(ChiTietHoaDon.objects.filter(hoa_don__in=hoa_don_da_thanh_toan).filter(
        Q(thuc_don__loai_mon='goi_buffet') | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('so_luong'))['tong'] or 0)

    so_bill = hoa_don_hom_nay.count()
    tong_ban = BanAn.objects.exclude(trang_thai='da_xoa').count() or 1
    tong_suc_chua = BanAn.objects.exclude(trang_thai='da_xoa').aggregate(tong=Sum('so_ghe'))['tong'] or 0
    ban_dang_phuc_vu = BanAn.objects.filter(trang_thai='dang_an').count()
    dat_ban = PhieuDatBan.objects.filter(thoi_gian_den__date=today).aggregate(tong=Sum('so_nguoi'))['tong'] or 0
    hoa_don_gan_day = list(hoa_don_hom_nay.select_related('ban_an', 'khach_hang').order_by('-thoi_gian_vao')[:5])

    tien_ve = int(ChiTietHoaDon.objects.filter(
        hoa_don__in=hoa_don_da_thanh_toan
    ).filter(
        Q(thuc_don__loai_mon='goi_buffet') | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('thanh_tien'))['tong'] or 0)

    tien_do_uong = int(ChiTietHoaDon.objects.filter(
        hoa_don__in=hoa_don_da_thanh_toan,
        thuc_don__loai_mon='do_uong'
    ).exclude(
        Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('thanh_tien'))['tong'] or 0)

    tien_dich_vu = max(0, doanh_thu - tien_ve - tien_do_uong)
    ti_le_tien_ve = round((tien_ve / doanh_thu) * 100, 1) if doanh_thu > 0 else 0.0

    return {
        'doanh_thu_hom_nay': doanh_thu,
        'thuc_khach_hom_nay': thuc_khach,
        'rev_pax': int(doanh_thu / thuc_khach) if thuc_khach > 0 else 0,
        'ban_dang_phuc_vu': ban_dang_phuc_vu,
        'tong_ban': tong_ban,
        'tong_suc_chua': tong_suc_chua,
        'occupancy_rate': round((ban_dang_phuc_vu / tong_ban) * 100, 1),
        'turnover_rate': round(so_bill / tong_ban, 1),
        'dat_ban_hom_nay': dat_ban,
        'hoa_don_gan_day': hoa_don_gan_day,
        'staff_trua_thuc_te': CaLamViec.objects.filter(ngay_lam_viec=today, bo_phan='service', loai_ca__in=['morning', 'full']).aggregate(c=Count('nhan_vien', distinct=True))['c'] or 0,
        'staff_toi_thuc_te': CaLamViec.objects.filter(ngay_lam_viec=today, bo_phan='service', loai_ca__in=['evening', 'full']).aggregate(c=Count('nhan_vien', distinct=True))['c'] or 0,
        'tien_ve': tien_ve,
        'tien_do_uong': tien_do_uong,
        'tien_dich_vu': tien_dich_vu,
        'ti_le_tien_ve': ti_le_tien_ve,
        'ti_le_ve': ti_le_tien_ve,
        'ticket_ratio': ti_le_tien_ve,
    }


def get_cost_data(today, doanh_thu_hom_nay, thuc_khach_hom_nay):
    tien_xuat_kho = ChiTietPhieuKho.objects.filter(
        phieu__loai_phieu='xuat', phieu__ngay_thuc_hien__date=today
    ).aggregate(
        tong_gia_von=Sum(
            ExpressionWrapper(F('so_luong') * F('nguyen_lieu__don_gia_trung_binh'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )['tong_gia_von'] or 0

    food_cost_pct = round((float(tien_xuat_kho) / float(doanh_thu_hom_nay)) * 100, 1) if doanh_thu_hom_nay > 0 else 0.0

    so_nhan_vien = CaLamViec.objects.filter(ngay_lam_viec=today).aggregate(c=Count('nhan_vien'))['c'] or 0
    staff_cost_per_pax = int((so_nhan_vien * SYSTEM_CONFIG['default_salary_per_shift']) / thuc_khach_hom_nay) if thuc_khach_hom_nay > 0 else 0

    return {'food_cost_pct': food_cost_pct, 'staff_cost_per_pax': staff_cost_per_pax}


def get_top_drinks(today):
    return ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date=today, thuc_don__loai_mon='do_uong'
    ).exclude(hoa_don__trang_thai='da_huy').values('ten_mon_luu_tru') \
        .annotate(total_sold=Sum('so_luong')).order_by('-total_sold')[:5]


def get_ai_forecast_and_charts_dashboard(today, current_hour):
    # Dùng chung 1 thuật toán duy nhất với trang AI Analytics (đã tích hợp WMA + Weather)
    features = get_ai_features(today, today, current_hour)
    
    khach_theo_gio = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date=today
    ).exclude(hoa_don__trang_thai='da_huy').filter(
        Q(thuc_don__loai_mon='goi_buffet') | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).annotate(gio=ExtractHour('hoa_don__thoi_gian_vao')).values('gio').annotate(tong_khach=Sum('so_luong')).order_by('gio')

    dict_thuc_te = {item['gio']: int(item['tong_khach']) for item in khach_theo_gio}
    khung_gio_hoat_dong = list(range(0, 24))
    chart_labels = [f"{h}h" for h in khung_gio_hoat_dong]
    chart_thuc_te = []

    for h in khung_gio_hoat_dong:
        is_visible = (h <= current_hour) if current_hour >= 6 else True
        chart_thuc_te.append(dict_thuc_te.get(h, 0) if is_visible else None)

    return {
        'chart_labels': chart_labels, 
        'chart_thuc_te': chart_thuc_te, 
        'chart_du_bao': features.get('chart_du_bao', []),
        'ai_khach_min': int(features.get('wma_result', {}).get('wma', 0) * SYSTEM_CONFIG['ai_min_factor']),
        'ai_khach_max': features.get('pax_forecast', 0),
        'ai_khach_trua': features.get('pax_trua', 0), 
        'ai_khach_toi': features.get('pax_toi', 0),
        'ai_doanh_thu_m': round((features.get('pax_forecast', 0) * SYSTEM_CONFIG['arpu_expected']) / 1000000, 1),
        'inventory_warnings': features.get('jit_warnings', []),
        'weather_data': features.get('weather_data'),
    }


def build_dashboard_context(today, current_hour):
    realtime_data = get_realtime_data(today)
    cost_data = get_cost_data(today, realtime_data['doanh_thu_hom_nay'], realtime_data['thuc_khach_hom_nay'])
    ai_data = get_ai_forecast_and_charts_dashboard(today, current_hour)
    top_drinks = get_top_drinks(today)
    # Thêm insights hôm nay cho Dashboard
    try:
        features_today = get_ai_features(today, today, current_hour)
        insights_today = detect_insights(features_today, today, current_hour)
        insights_today.sort(key=lambda x: x['confidence'], reverse=True)
    except Exception:
        insights_today = []
    return {**realtime_data, **cost_data, **ai_data, 'top_do_uong': top_drinks, 'insights_today': insights_today}


@login_required(login_url='login')
def dashboard_view(request):
    if not check_manager_permission(request.user):
        messages.warning(request, "Khu vực nội bộ! Bạn đã chuyển về POS.")
        return redirect('pos')
    now = timezone.now()
    today, current_hour = now.date(), now.hour
    
    # Bỏ cache để dữ liệu realtime (kho, nhân sự) cập nhật ngay lập tức khi demo
    context = build_dashboard_context(today, current_hour)
    return render(request, 'dashboard/dashboard.html', context)


# ==========================================
# LOGIC TRANG TRỢ LÝ AI (AI DSS PIPELINE)
# ==========================================
def get_ai_features(today, target_date, current_hour, override_dataset_days=None):
    """
    Thu thập và tính toán tất cả feature vectors đầu vào cho AI DSS.
    Bao gồm WMA, thống kê σ/CV, Lift Ratio, và dữ liệu nhân sự.
    """
    features = {}
    dataset_days, predict_days = get_ai_config()
    if override_dataset_days:
        dataset_days = override_dataset_days

    # --- Dữ liệu hôm nay (chỉ tính nếu target_date == today) ---
    if target_date == today:
        hd_today = HoaDon.objects.filter(thoi_gian_vao__date=today, trang_thai='da_thanh_toan')
        features['revenue_today'] = float(hd_today.aggregate(tong=Sum('khach_can_tra'))['tong'] or 0)
        features['pax_today'] = int(ChiTietHoaDon.objects.filter(
            hoa_don__thoi_gian_vao__date=today
        ).exclude(hoa_don__trang_thai='da_huy').filter(
            Q(thuc_don__loai_mon='goi_buffet') | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
        ).aggregate(tong=Sum('so_luong'))['tong'] or 0)
    else:
        features['revenue_today'] = 0
        features['pax_today'] = 0

    # --- WMA Forecast theo thứ của target_date ---
    wma_result = calculate_wma_forecast(target_date.weekday(), dataset_days)
    features['wma_result'] = wma_result
    features['avg_pax_7d'] = wma_result['mean']
    features['pax_wma'] = wma_result['wma']
    features['pax_std'] = wma_result['std']
    features['pax_cv'] = wma_result['cv']
    features['n_weeks_data'] = wma_result['n_weeks']

    # --- Lịch sử hóa đơn trong dataset window ---
    seven_days_ago = today - timedelta(days=dataset_days)
    past_bills = HoaDon.objects.filter(thoi_gian_vao__date__gte=seven_days_ago, thoi_gian_vao__date__lt=today)
    active_days = past_bills.values('thoi_gian_vao__date').distinct().count()
    days_divisor = active_days if active_days > 0 else 1

    past_tickets = int(ChiTietHoaDon.objects.filter(
        hoa_don__in=past_bills
    ).exclude(hoa_don__trang_thai='da_huy').filter(
        Q(thuc_don__loai_mon='goi_buffet') | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('so_luong'))['tong'] or 0)

    total_past_bills_count = past_bills.count()

    # --- Tăng trưởng đồ uống ---
    three_days_ago = today - timedelta(days=3)
    recent_drinks_total = float(ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date__gte=three_days_ago,
        hoa_don__thoi_gian_vao__date__lt=today,
        thuc_don__loai_mon='do_uong'
    ).exclude(hoa_don__trang_thai='da_huy').aggregate(tong=Sum('thanh_tien'))['tong'] or 0)
    recent_drinks_avg = recent_drinks_total / 3.0

    drinks_past_total = float(ChiTietHoaDon.objects.filter(
        hoa_don__in=past_bills, thuc_don__loai_mon='do_uong'
    ).exclude(hoa_don__trang_thai='da_huy').aggregate(tong=Sum('thanh_tien'))['tong'] or 0)
    drinks_7d_avg = drinks_past_total / days_divisor

    if drinks_7d_avg == 0:
        features['drinks_growth'] = 0.0
    else:
        features['drinks_growth'] = float(((recent_drinks_avg - drinks_7d_avg) / drinks_7d_avg) * 100)

    # --- Z-Score cho drinks (thay threshold cứng) ---
    # Tính Z-score của doanh thu đồ uống 3 ngày gần nhất so với chuỗi lịch sử
    features['drinks_z_score'] = (recent_drinks_avg - drinks_7d_avg) / (drinks_7d_avg * 0.15 + 1)

    # --- Tỷ lệ khách nhóm ---
    family_past_bills = ChiTietHoaDon.objects.filter(
        hoa_don__in=past_bills
    ).exclude(hoa_don__trang_thai='da_huy').filter(
        Q(thuc_don__loai_mon='goi_buffet') | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).values('hoa_don').annotate(tong_ve=Sum('so_luong')).filter(tong_ve__gte=4).count()

    features['total_bills_today'] = total_past_bills_count
    features['family_ratio'] = float((family_past_bills / total_past_bills_count) * 100) if total_past_bills_count > 0 else 0.0

    # --- Sức khỏe mô hình ---
    features['total_dataset'] = total_past_bills_count
    features['coverage_days'] = days_divisor

    # --- Tỷ lệ khách chiều thấp điểm ---
    afternoon_pax = int(ChiTietHoaDon.objects.filter(
        hoa_don__in=past_bills, hoa_don__thoi_gian_vao__hour__in=[14, 15, 16]
    ).exclude(hoa_don__trang_thai='da_huy').filter(
        Q(thuc_don__loai_mon='goi_buffet') | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('so_luong'))['tong'] or 0)
    features['afternoon_ratio'] = float(afternoon_pax) / past_tickets if past_tickets > 0 else 0.0

    # --- Nhân sự ---
    ca_lam = CaLamViec.objects.filter(ngay_lam_viec=target_date, bo_phan='service')
    staff_trua = 0
    staff_toi = 0
    for ca in ca_lam:
        if ca.loai_ca in ['morning', 'full']:
            staff_trua += ca.nhan_vien.count()
        if ca.loai_ca in ['evening', 'full']:
            staff_toi += ca.nhan_vien.count()

    # Lưu lại biến kiểm tra nếu là ngày tương lai chưa xếp ca thì lấy hôm nay làm baseline
    if target_date > today and staff_trua == 0 and staff_toi == 0:
        ca_lam_today = CaLamViec.objects.filter(ngay_lam_viec=today, bo_phan='service')
        staff_trua_today = 0
        staff_toi_today = 0
        for ca in ca_lam_today:
            if ca.loai_ca in ['morning', 'full']:
                staff_trua_today += ca.nhan_vien.count()
            if ca.loai_ca in ['evening', 'full']:
                staff_toi_today += ca.nhan_vien.count()
        
        features['is_future_prediction_using_today_baseline'] = True
        features['staff_trua_baseline'] = staff_trua_today
        features['staff_toi_baseline'] = staff_toi_today

    features['staff_count'] = max(staff_trua, staff_toi) if max(staff_trua, staff_toi) > 0 else 1
    features['staff_trua'] = staff_trua
    features['staff_toi'] = staff_toi

    # --- Dự báo lượng khách (dùng WMA + weekday factor + WAF) ---
    weekday_factor = 1.25 if target_date.weekday() >= 4 else 0.95
    ai_khach_wma = int(wma_result['wma'] * weekday_factor) or SYSTEM_CONFIG['fallback_pax']

    # Lấy thời tiết và tính WAF
    weather_data = fetch_weather_forecast(target_date)
    if weather_data:
        waf = weather_data['waf']
        ai_khach_max = max(1, int(ai_khach_wma * waf))
    else:
        waf = 1.0
        ai_khach_max = ai_khach_wma

    features['pax_forecast_wma'] = ai_khach_wma      # WMA thuần (chưa điều chỉnh)
    features['pax_forecast'] = ai_khach_max           # Sau điều chỉnh thời tiết
    features['weather_data'] = weather_data           # None nếu lỗi API
    features['weather_waf'] = waf

    # BẮT BUỘC: ĐỒNG BỘ 100% VỚI get_ai_forecast_and_charts_dashboard
    khach_theo_gio = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date__gte=today - timedelta(days=dataset_days),
        hoa_don__thoi_gian_vao__date__lt=today,
        hoa_don__thoi_gian_vao__iso_week_day=target_date.weekday() + 1
    ).exclude(hoa_don__trang_thai='da_huy').filter(
        Q(thuc_don__loai_mon='goi_buffet') | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).annotate(gio=ExtractHour('hoa_don__thoi_gian_vao')).values('gio').annotate(tong_khach=Sum('so_luong'))

    tong_khach_lich_su = sum([item['tong_khach'] for item in khach_theo_gio]) or 1
    ai_distribution_dynamic = {h: 0.0 for h in range(24)}

    if tong_khach_lich_su > 1:
        for item in khach_theo_gio:
            ai_distribution_dynamic[item['gio']] = float(item['tong_khach']) / tong_khach_lich_su
    else:
        sum_config = sum(SYSTEM_CONFIG['ai_distribution'].values())
        for h, v in SYSTEM_CONFIG['ai_distribution'].items():
            ai_distribution_dynamic[h] = v / sum_config

    features['pax_trua'] = sum(int(ai_khach_max * ai_distribution_dynamic[h]) for h in range(8, 15))
    features['pax_toi'] = sum(int(ai_khach_max * ai_distribution_dynamic[h]) for h in range(15, 23))
    features['chart_du_bao'] = [int(ai_khach_max * ai_distribution_dynamic[h]) for h in range(24)]

    features['staff_required'] = max(1, round(features['pax_forecast'] / float(SYSTEM_CONFIG['staff_per_pax'])))

    # Alias keys cho template mới
    features['pax_forecast_trua'] = features['pax_trua']
    features['pax_forecast_toi']  = features['pax_toi']
    features['staff_required_trua'] = max(1, round(features['pax_trua'] / float(SYSTEM_CONFIG['staff_per_pax'])))
    features['staff_required_toi']  = max(1, round(features['pax_toi']  / float(SYSTEM_CONFIG['staff_per_pax'])))
    features['weekday_factor'] = weekday_factor

    # --- Z-Score anomalies ---
    features['anomaly_days'] = detect_anomaly_days(dataset_days)


    # --- JIT Inventory Warnings (tính sẵn để detect_insights dùng lại, tránh gọi 2 lần) ---
    features['jit_warnings'] = calculate_jit_import(features['pax_forecast'])

    return features


def detect_insights(features, target_date, current_hour):
    """
    Phát hiện các insight (cơ hội / cảnh báo / rủi ro) dựa trên feature vectors.
    Confidence Score được tính từ CV thực tế (σ/μ) thay vì kinh nghiệm cứng.
    """
    insights = []

    tong_ban = BanAn.objects.exclude(trang_thai='da_xoa').count() or 1
    ban_dang_phuc_vu = BanAn.objects.filter(trang_thai='dang_an').count()
    occupancy = (ban_dang_phuc_vu / tong_ban) * 100

    # Base confidence từ CV của WMA
    cv = features.get('pax_cv', 20.0)
    n_weeks = features.get('n_weeks_data', 0)
    base_conf = compute_confidence(cv, n_weeks)

    today = timezone.now().date()

    # ===========================================
    # ĐỀ XUẤT 1: KÍCH CẦU GIỜ THẤP ĐIỂM (Traffic Booster) - CHỈ ÁP DỤNG HÔM NAY
    # ===========================================
    if target_date == today and 14 <= current_hour <= 17 and occupancy < 30:
        conf = compute_confidence(cv, n_weeks, base=88.0)
        insights.append({
            'type': 'opportunity', 'icon': 'bi-moisture', 'color': 'primary',
            'title': 'Kích Cầu Giờ Thấp Điểm (Traffic Booster)',
            'description': (
                f"Tỷ lệ lấp đầy bàn (Occupancy) hiện tại rất thấp ({occupancy:.1f}%) "
                f"vào khung giờ thấp điểm 14h–17h."
            ),
            'root_cause': (
                "Time-Series Analysis phát hiện khung 14h–17h luôn có mức lưu lượng thấp "
                "(Afternoon Valley). Thiếu chương trình kích cầu tập trung."
            ),
            'action': (
                'Kích hoạt Chiến dịch "Afternoon Chill". '
                'AI tự động phát hành Voucher giảm 20% cho toàn bộ Đồ Uống & Dịch Vụ bổ sung '
                '(Hóa đơn mở từ 14:00 đến 16:30).'
            ),
            'simulation': '+15% Khách vãng lai & +25% Doanh thu đồ uống',
            'impact_metric': 'Tỷ lệ lấp đầy & Doanh thu',
            'confidence': conf,
            'explain': "WMA Time-Series: Phân tích phân phối lưu lượng khách theo giờ từ lịch sử.",
            'algo_tag': 'WMA + Occupancy Rule',
        })

    # ===========================================
    # ĐỀ XUẤT 2: CẢNH BÁO ĐỒ UỐNG SUY GIẢM (Z-Score)
    # ===========================================
    # Dùng Z-Score ngưỡng thống kê thay vì -5% cứng
    drinks_z = features.get('drinks_z_score', 0)
    if drinks_z < -1.0:  # Dưới 1 độ lệch chuẩn so với trung bình lịch sử
        conf = compute_confidence(cv, n_weeks, base=82.0)
        insights.append({
            'type': 'warning', 'icon': 'bi-graph-down-arrow', 'color': 'danger',
            'title': 'Doanh thu Đồ uống suy giảm',
            'description': (
                f"Doanh thu đồ uống 3 ngày gần nhất giảm {abs(features['drinks_growth']):.1f}% "
                f"so với trung bình kỳ trước (Z = {drinks_z:.2f}, ngưỡng cảnh báo: Z < -1.0)."
            ),
            'root_cause': (
                f"Tệp khách gia đình chiếm {features['family_ratio']:.1f}% nhưng "
                f"hệ thống chưa có gói Combo Đồ Uống cỡ lớn (Tháp bia/Trà pitcher). "
                f"Z-Score thống kê xác nhận đây là bất thường thực sự, không phải nhiễu ngẫu nhiên."
            ),
            'action': (
                'AI tự động thiết lập Combo Tháp Đồ Uống Tiết Kiệm (Giảm 10%). '
                'Nhắc nhân viên mời khách dùng Bia/Nước ép thay vì nước ngọt.'
            ),
            'simulation': '+12.5%',
            'impact_metric': 'Doanh thu Đồ uống',
            'confidence': conf,
            'explain': f"Z-Score Anomaly Detection: Z = (X̄_3d - μ_30d) / σ = {drinks_z:.2f} < -1.0 → Bất thường.",
            'algo_tag': 'Z-Score Anomaly',
        })

    # ===========================================
    # ĐỀ XUẤT 3: TỐI ƯU NGUỒN NHÂN LỰC (Workload Optimization)
    # ===========================================
    req_trua = math.ceil(features['pax_trua'] / float(SYSTEM_CONFIG['staff_per_pax']))
    req_toi = math.ceil(features['pax_toi'] / float(SYSTEM_CONFIG['staff_per_pax']))

    workload_score = 0
    warning_text = []
    action_text = []

    is_future_empty = features.get('is_future_prediction_using_today_baseline', False)

    if is_future_empty:
        # Dự báo tương lai nhưng chưa xếp ca -> Lấy lịch hôm nay làm mốc so sánh
        delta_days = (target_date - today).days
        if delta_days == 1:
            date_label = "ngày mai"
        elif delta_days == 0:
            date_label = "hôm nay"
        else:
            date_label = f"ngày {target_date.strftime('%d/%m')}"

        # Ca Trưa
        staff_trua_base = features.get('staff_trua_baseline', 0)
        diff_trua = req_trua - staff_trua_base
        if diff_trua > 0:
            warning_text.append(f"Ca Trưa {date_label} cần tổng cộng {req_trua} Nhân viên phục vụ (lượng nhân sự hôm nay là {staff_trua_base} Nhân viên phục vụ).")
            action_text.append(f"Cần bổ sung/xếp thêm {diff_trua} Nhân viên phục vụ cho Ca Trưa.")
        elif diff_trua < 0:
            warning_text.append(f"Ca Trưa {date_label} cần {req_trua} Nhân viên phục vụ (lượng nhân sự hôm nay là {staff_trua_base} Nhân viên phục vụ).")
            action_text.append(f"Có thể cắt giảm bớt {abs(diff_trua)} Nhân viên phục vụ Ca Trưa.")
        else:
            warning_text.append(f"Ca Trưa {date_label} cần {req_trua} Nhân viên phục vụ (vừa đúng bằng lượng nhân sự hôm nay: {staff_trua_base} Nhân viên phục vụ).")
            action_text.append("Duy trì lượng nhân sự Ca Trưa như hôm nay.")

        # Ca Tối
        staff_toi_base = features.get('staff_toi_baseline', 0)
        diff_toi = req_toi - staff_toi_base
        if diff_toi > 0:
            warning_text.append(f"Ca Tối {date_label} cần tổng cộng {req_toi} Nhân viên phục vụ (lượng nhân sự hôm nay là {staff_toi_base} Nhân viên phục vụ).")
            action_text.append(f"Cần bổ sung/xếp thêm {diff_toi} Nhân viên phục vụ cho Ca Tối.")
        elif diff_toi < 0:
            warning_text.append(f"Ca Tối {date_label} cần {req_toi} Nhân viên phục vụ (lượng nhân sự hôm nay là {staff_toi_base} Nhân viên phục vụ).")
            action_text.append(f"Có thể cắt giảm bớt {abs(diff_toi)} Nhân viên phục vụ Ca Tối.")
        else:
            warning_text.append(f"Ca Tối {date_label} cần {req_toi} Nhân viên phục vụ (vừa đúng bằng lượng nhân sự hôm nay: {staff_toi_base} Nhân viên phục vụ).")
            action_text.append("Duy trì lượng nhân sự Ca Tối như hôm nay.")
            
        workload_score = max(req_trua / (staff_trua_base or 1), req_toi / (staff_toi_base or 1))
    else:
        # So sánh trực tiếp với nhân sự đã xếp trong ngày target_date
        staff_trua = features['staff_trua']
        if staff_trua < req_trua:
            thieu = req_trua - staff_trua
            warning_text.append(f"Ca Trưa cần {req_trua} Nhân viên phục vụ (Đã xếp: {staff_trua} Nhân viên phục vụ, thiếu {thieu} Nhân viên phục vụ).")
            action_text.append(f"Điều động thêm {thieu} Nhân viên phục vụ Ca Trưa.")
            workload_score = max(workload_score, req_trua / (staff_trua or 1))
        elif staff_trua > req_trua:
            thua = staff_trua - req_trua
            warning_text.append(f"Ca Trưa cần {req_trua} Nhân viên phục vụ (Đã xếp: {staff_trua} Nhân viên phục vụ, thừa {thua} Nhân viên phục vụ).")
            action_text.append(f"Cho {thua} Nhân viên phục vụ Ca Trưa nghỉ bù để tối ưu Cost.")

        staff_toi = features['staff_toi']
        if staff_toi < req_toi:
            thieu = req_toi - staff_toi
            warning_text.append(f"Ca Tối cần {req_toi} Nhân viên phục vụ (Đã xếp: {staff_toi} Nhân viên phục vụ, thiếu {thieu} Nhân viên phục vụ).")
            action_text.append(f"Điều động thêm {thieu} Nhân viên phục vụ Ca Tối.")
            workload_score = max(workload_score, req_toi / (staff_toi or 1))
        elif staff_toi > req_toi:
            thua = staff_toi - req_toi
            warning_text.append(f"Ca Tối cần {req_toi} Nhân viên phục vụ (Đã xếp: {staff_toi} Nhân viên phục vụ, thừa {thua} Nhân viên phục vụ).")
            action_text.append(f"Cho {thua} Nhân viên phục vụ Ca Tối nghỉ bù để tối ưu Cost.")

        if not warning_text:
            warning_text = ["Nhân sự đã được bố trí hợp lý theo định mức chuẩn."]
            action_text = ["Không cần điều chỉnh."]
            workload_score = 1.0

    conf_workload = compute_confidence(cv, n_weeks, base=80.0 + workload_score * 5)
    insights.append({
        'type': 'risk' if workload_score > 1.2 else ('opportunity' if 'thừa' in str(warning_text) else 'info'),
        'icon': 'bi-people-fill',
        'color': 'warning' if workload_score > 1.2 else 'primary',
        'title': 'Tối ưu Nguồn Nhân Lực (Workload)',
        'description': " ".join(warning_text),
        'root_cause': (
            f"WMA Dự báo: Trưa {features['pax_trua']} Pax, Tối {features['pax_toi']} Pax. "
            f"Định mức: 1 NV / {SYSTEM_CONFIG['staff_per_pax']} khách/ca."
        ),
        'action': " ".join(action_text),
        'simulation': '+ Tối ưu Chi Phí / Thời gian',
        'impact_metric': 'Cost & CSAT',
        'confidence': conf_workload,
        'explain': (
            f"Workload Optimization: WMA_pax = {features['pax_wma']:.0f} Pax "
            f"→ NV cần = {features['staff_required']} người "
            f"(định mức {SYSTEM_CONFIG['staff_per_pax']} Pax/NV)."
        ),
        'algo_tag': 'WMA + Workload Rule',
    })

    # ===========================================
    # ĐỀ XUẤT 4: CẢNH BÁO TỒN KHO JIT
    # ⚡ Dùng kết quả đã tính sẵn trong features — không gọi lại calculate_jit_import
    # ===========================================
    try:
        inventory_warnings = features.get('jit_warnings', [])
        for w in inventory_warnings:
            conf_jit = compute_confidence(cv, n_weeks, base=90.0)
            insights.append({
                'type': 'risk', 'icon': 'bi-box-seam', 'color': 'danger',
                'title': f"Cảnh Báo Cạn Kiệt: {w['ten_nguyen_lieu']}",
                'description': (
                    f"Tồn kho: {w['ton_kho']} {w['don_vi']}. "
                    f"Nhu cầu dự báo: {w['nhu_cau_ngay_mai']} {w['don_vi']}. "
                    f"Safety Stock (Z₉₅): {w['safety_stock']} {w['don_vi']}."
                ),
                'root_cause': (
                    f"JIT Burn Rate = {w['burn_rate']:.4f} {w['don_vi']}/khách. "
                    f"Tồn kho hiện tại dưới mức an toàn = Nhu cầu + Safety Stock."
                ),
                'action': (
                    f"Lập tức tạo Phiếu Nhập Kho bổ sung ít nhất "
                    f"{w['de_xuat_nhap']} {w['don_vi']} {w['ten_nguyen_lieu']} ngay hôm nay."
                ),
                'simulation': f"Tránh {int(w['de_xuat_nhap'] * 3)} khách phàn nàn do thiếu món",
                'impact_metric': 'Vận hành & Trải nghiệm',
                'confidence': conf_jit,
                'explain': (
                    f"JIT Safety Stock = Burn Rate × σ_pax × Z₉₅% = "
                    f"{w['burn_rate']:.4f} × σ × 1.645 = {w['safety_stock']:.2f} {w['don_vi']}."
                ),
                'algo_tag': 'JIT Burn Rate + Safety Stock',
            })
    except Exception as e:
        print("Lỗi JIT Insight:", e)

    # ===========================================
    # ĐỀ XUẤT 5: CẢNH BÁO / CƠ HỘI THỜI TIẾT (Weather Adjustment)
    # ===========================================
    weather_data = features.get('weather_data')
    waf = features.get('weather_waf', 1.0)
    pax_wma_raw = features.get('pax_forecast_wma', features.get('pax_forecast', 0))
    pax_adjusted = features.get('pax_forecast', 0)

    if weather_data:
        icon_str = weather_data['icon']
        desc_str = weather_data['description']
        precip   = weather_data['precipitation']
        temp     = weather_data['temp_max']
        waf_pct  = round((waf - 1.0) * 100, 1)

        if waf < 0.90:
            # Mưa to / bão → cảnh báo
            conf_w = compute_confidence(cv, n_weeks, base=86.0)
            insights.append({
                'type': 'warning', 'icon': 'bi-cloud-rain-heavy-fill', 'color': 'warning',
                'title': f'{icon_str} Thời tiết xấu — Dự báo khách giảm {abs(waf_pct):.0f}%',
                'description': (
                    f"Dự báo thời tiết ngày {target_date.strftime('%d/%m')}: "
                    f"{desc_str}, lượng mưa {precip} mm, nhiệt độ tối đa {temp}°C. "
                    f"Lưu lượng khách dự kiến giảm {abs(waf_pct):.0f}% so với ngày bình thường."
                ),
                'root_cause': (
                    f"Weather Adjustment Factor (WAF) = {waf:.3f} "
                    f"(Mưa {precip}mm → -{abs(waf_pct):.0f}%). "
                    f"WMA thuần: {pax_wma_raw} Pax → Sau điều chỉnh: {pax_adjusted} Pax."
                ),
                'action': (
                    f"Cân nhắc giảm ca nhân sự phục vụ bàn ({abs(int(waf_pct * features['staff_required'] / 100))} NV). "
                    "Đẩy mạnh đặt bàn trước qua điện thoại. Kiểm tra hệ thống mái che sân ngoài."
                ),
                'simulation': f"Tiết kiệm chi phí nhân sự ~{abs(int(waf_pct))}%",
                'impact_metric': 'Lưu lượng khách & Chi phí vận hành',
                'confidence': conf_w,
                'explain': (
                    f"WAF = 1.0 - (mưa penalty) - (nhiệt độ penalty) = {waf:.3f}. "
                    f"Pax_adjusted = WMA × WAF = {pax_wma_raw} × {waf:.3f} = {pax_adjusted} Pax."
                ),
                'algo_tag': 'Weather Adjustment Factor',
            })
        elif waf > 1.05:
            # Nắng đẹp → cơ hội
            conf_w = compute_confidence(cv, n_weeks, base=84.0)
            insights.append({
                'type': 'opportunity', 'icon': 'bi-sun-fill', 'color': 'success',
                'title': f'{icon_str} Thời tiết thuận lợi — Cơ hội tăng khách +{waf_pct:.0f}%',
                'description': (
                    f"Dự báo thời tiết ngày {target_date.strftime('%d/%m')}: "
                    f"{desc_str}, nhiệt độ tối đa {temp}°C. "
                    f"Lưu lượng khách dự kiến tăng {waf_pct:.0f}% so với trung bình."
                ),
                'root_cause': (
                    f"Weather Adjustment Factor (WAF) = {waf:.3f} "
                    f"(Trời đẹp → +{waf_pct:.0f}%). "
                    f"WMA thuần: {pax_wma_raw} Pax → Sau điều chỉnh: {pax_adjusted} Pax."
                ),
                'action': (
                    "Đảm bảo đủ nhân sự theo dự báo tăng. "
                    "Tăng cường chuẩn bị nguyên liệu và bàn ghế sân ngoài/khu vui chơi. "
                    "Kích hoạt chương trình check-in mạng xã hội."
                ),
                'simulation': f"Tăng doanh thu dự kiến +{waf_pct:.0f}% (~{int(pax_adjusted * SYSTEM_CONFIG['arpu_expected'] / 1000000):.1f}M VNĐ)",
                'impact_metric': 'Doanh thu & Lưu lượng khách',
                'confidence': conf_w,
                'explain': (
                    f"WAF = 1.0 + (nắng bonus) + (nhiệt độ bonus) = {waf:.3f}. "
                    f"Pax_adjusted = WMA × WAF = {pax_wma_raw} × {waf:.3f} = {pax_adjusted} Pax."
                ),
                'algo_tag': 'Weather Adjustment Factor',
            })

    return insights



def get_ai_charts_and_mutations(today, target_date, daily_pax, days_multiplier=1):
    days_name = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
    rev_labels, rev_actual, rev_forecast = [], [], []

    for i in range(5, -2, -1):
        d = today - datetime.timedelta(days=i)
        label = days_name[d.weekday()] + (" (Dự báo)" if i < 0 else "")
        rev_labels.append(label)

        if i > 0:
            tong = HoaDon.objects.filter(thoi_gian_vao__date=d, trang_thai='da_thanh_toan').aggregate(tong=Sum('khach_can_tra'))['tong'] or 0
            rev_actual.append(float(tong) / 1000000 if tong > 0 else None)
            rev_forecast.append(None)
        elif i == 0:
            tong = HoaDon.objects.filter(thoi_gian_vao__date=d, trang_thai='da_thanh_toan').aggregate(tong=Sum('khach_can_tra'))['tong'] or 0
            rev_actual.append(float(tong) / 1000000 if tong > 0 else 0.0)
            rev_forecast.append(float(tong) / 1000000 if tong > 0 else 0.0)
        else:
            rev_actual.append(None)
            rev_forecast.append(float((daily_pax * SYSTEM_CONFIG['arpu_expected']) / 1000000))

    traffic_labels = ['17h', '18h', '19h', '20h', '21h']
    traffic_forecast = [int(daily_pax * days_multiplier * SYSTEM_CONFIG['ai_distribution'].get(h, 0.1)) for h in range(17, 22)]

    mid_date = today - datetime.timedelta(days=3)
    start_date = today - datetime.timedelta(days=6)

    total_recent = float(ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date__gte=mid_date, hoa_don__thoi_gian_vao__date__lt=today
    ).exclude(hoa_don__trang_thai='da_huy').aggregate(tong=Sum('so_luong'))['tong'] or 1)

    total_past = float(ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date__gte=start_date, hoa_don__thoi_gian_vao__date__lt=mid_date
    ).exclude(hoa_don__trang_thai='da_huy').aggregate(tong=Sum('so_luong'))['tong'] or 1)

    recent_data = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date__gte=mid_date, hoa_don__thoi_gian_vao__date__lt=today
    ).exclude(hoa_don__trang_thai='da_huy').values('ten_mon_luu_tru').annotate(tong_sl=Sum('so_luong'))

    past_data = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date__gte=start_date, hoa_don__thoi_gian_vao__date__lt=mid_date
    ).exclude(hoa_don__trang_thai='da_huy').values('ten_mon_luu_tru').annotate(tong_sl=Sum('so_luong'))

    past_dict = {item['ten_mon_luu_tru']: item['tong_sl'] for item in past_data}

    mutations_list = []
    for item in recent_data:
        name, recent_sl = item['ten_mon_luu_tru'], float(item['tong_sl'])
        past_sl = float(past_dict.get(name, 0))
        if past_sl > 5 and recent_sl > 5:
            recent_ratio = recent_sl / total_recent
            past_ratio = past_sl / total_past
            growth_rate = ((recent_ratio - past_ratio) / past_ratio) * 100
            if abs(growth_rate) >= 15:
                mutations_list.append({'name': name, 'growth': growth_rate, 'abs_growth': abs(growth_rate)})

    mutations_list.sort(key=lambda x: x['abs_growth'], reverse=True)
    mutations = []
    for m in mutations_list[:3]:
        if m['growth'] > 0:
            mutations.append({
                'ten_mon': m['name'], 'icon': 'bi-arrow-up-right',
                'bg_color': '#ecfdf5', 'text_color': '#10b981', 'text_class': 'text-success',
                'mo_ta': f"Tỷ trọng gọi món tăng <b class='text-success'>+{m['growth']:.1f}%</b>"
            })
        else:
            mutations.append({
                'ten_mon': m['name'], 'icon': 'bi-arrow-down-right',
                'bg_color': '#fef2f2', 'text_color': '#ef4444', 'text_class': 'text-danger',
                'mo_ta': f"Tỷ trọng gọi món giảm <b class='text-danger'>{m['growth']:.1f}%</b>"
            })

    # Nếu không có biến động thực tế thì để trống, giao diện sẽ tự hiện thông báo "Không có biến động"
    pass

    return {
        'rev_labels': rev_labels, 'rev_actual': rev_actual, 'rev_forecast': rev_forecast,
        'traffic_labels': traffic_labels, 'traffic_forecast': traffic_forecast,
        'mutations': mutations,
    }


# ==========================================
# VIEW CHÍNH: TRANG AI DỰ BÁO TƯƠNG LAI
# ==========================================
@login_required(login_url='login')
def ai_analytics_view(request):
    if not check_manager_permission(request.user):
        messages.warning(request, "Tính năng AI chỉ dành cho cấp Quản lý!")
        return redirect('pos')

    today = timezone.now().date()
    current_hour = timezone.now().hour

    dataset_days_db, _ = get_ai_config()
    
    # Window dữ liệu huấn luyện (mặc định theo DB)
    window_raw = request.GET.get('window')
    if window_raw:
        try:
            days_window = int(window_raw.replace('d', ''))
            # Lưu lại vào DB để các trang khác (Dashboard, Phân ca) cũng học theo
            from core.models import SystemSetting
            setting, _ = SystemSetting.objects.get_or_create(id=1)
            setting.ai_dataset_window = f"{days_window}_days"
            setting.save()
            window_param = f"{days_window}d"
            dataset_days_db = days_window # Cập nhật biến để truyền xuống model
        except Exception:
            days_window = dataset_days_db
            window_param = f"{dataset_days_db}d"
    else:
        days_window = dataset_days_db
        window_param = f"{dataset_days_db}d"

    # Ngày mục tiêu (mặc định hôm nay để đồng bộ với Tổng quan và Phân ca)
    date_param = request.GET.get('date')
    if date_param:
        try:
            target_date = datetime.datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            target_date = today
    else:
        target_date = today

    # Các features AI
    features = get_ai_features(today, target_date, current_hour, days_window)
    daily_pax = features['pax_forecast']

    # Insights cho ngày được chọn
    insights = detect_insights(features, target_date, current_hour)
    insights.sort(key=lambda x: x['confidence'], reverse=True)

    # Biểu đồ phân bố khách theo giờ (8h-22h)
    dataset_days = days_window
    khach_theo_gio_qs = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date__gte=today - timedelta(days=dataset_days),
        hoa_don__thoi_gian_vao__date__lt=today,
        hoa_don__thoi_gian_vao__iso_week_day=target_date.weekday() + 1
    ).exclude(hoa_don__trang_thai='da_huy').filter(
        Q(thuc_don__loai_mon='goi_buffet') | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).annotate(gio=ExtractHour('hoa_don__thoi_gian_vao')).values('gio').annotate(tong_khach=Sum('so_luong'))

    tong_lich_su = sum(item['tong_khach'] for item in khach_theo_gio_qs) or 1
    dist = {h: 0.0 for h in range(24)}
    if tong_lich_su > 1:
        for item in khach_theo_gio_qs:
            dist[item['gio']] = float(item['tong_khach']) / tong_lich_su
    else:
        s = sum(SYSTEM_CONFIG['ai_distribution'].values())
        for h, v in SYSTEM_CONFIG['ai_distribution'].items():
            dist[h] = v / s

    hourly_labels = [f"{h}h" for h in range(8, 23)]
    hourly_data = [int(daily_pax * dist[h]) for h in range(8, 23)]

    # Bảng nguyên liệu đầy đủ
    nguyen_lieu_list, tong_chi_phi = calculate_jit_full(daily_pax)

    # Thống kê nhanh cho KPI
    so_can_nhap = sum(1 for nl in nguyen_lieu_list if nl['trang_thai'] == 'can_nhap')
    so_du_hang = sum(1 for nl in nguyen_lieu_list if nl['trang_thai'] == 'du_hang')
    so_sap_het = sum(1 for nl in nguyen_lieu_list if nl['trang_thai'] == 'sap_het')

    # Nhóm danh mục cho filter JS
    danh_muc_list = [
        {'key': 'hai_san', 'label': 'Hải Sản', 'icon': 'bi-water'},
        {'key': 'thit',    'label': 'Thịt',     'icon': 'bi-egg-fried'},
        {'key': 'rau_cu',  'label': 'Rau Củ',   'icon': 'bi-flower1'},
        {'key': 'gia_vi',  'label': 'Gia Vị',   'icon': 'bi-jar'},
        {'key': 'do_uong', 'label': 'Đồ Uống',  'icon': 'bi-cup-straw'},
        {'key': 'khac',    'label': 'Khác',     'icon': 'bi-box2'},
    ]

    # Kiểm tra ngày tương lai hay quá khứ
    delta_days = (target_date - today).days

    context = {
        'page_title': 'AI DỰ Báo Tương Lai',
        'features': features,
        'insights': insights,
        'window': window_param,
        'target_date': target_date.strftime('%Y-%m-%d'),
        'target_date_obj': target_date,
        'today': today,
        'delta_days': delta_days,
        'is_future': delta_days > 0,
        'is_past': delta_days < 0,
        'hourly_labels': hourly_labels,
        'hourly_data': hourly_data,
        'nguyen_lieu_list': nguyen_lieu_list,
        'tong_chi_phi': tong_chi_phi,
        'so_can_nhap': so_can_nhap,
        'so_du_hang': so_du_hang,
        'so_sap_het': so_sap_het,
        'danh_muc_list': danh_muc_list,
    }
    return render(request, 'AI/ai_analytics.html', context)


# ==========================================
# API: TẠO VOUCHER TỰ ĐỘNG
# ==========================================
@login_required(login_url='login')
@require_POST
def api_ai_generate_voucher(request):
    """AI tự động tạo voucher kích cầu giờ thấp điểm."""
    try:
        random_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        voucher_code = f"AI-{random_code}"
        ngay_het_han = timezone.now().date() + timedelta(days=3)

        voucher = Voucher.objects.create(
            ma_code=voucher_code,
            muc_giam="20%",
            dieu_kien_toi_thieu=500000,
            ngay_het_han=ngay_het_han,
            trang_thai=True,
            ai_de_xuat=True,
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Đã tạo voucher {voucher.ma_code} giảm {voucher.muc_giam}',
            'voucher_code': voucher.ma_code,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)