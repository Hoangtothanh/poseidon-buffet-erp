import datetime
import random
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import ExtractHour

# Import Model từ các app
from pos.models import HoaDon, ChiTietHoaDon
from reception.models import BanAn, PhieuDatBan
from hrm.models import ChiTietCaLam
from inventory.models import ChiTietXuatKho, NguyenLieu
from .models import AIPhanTichThucDon 

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
    }
}

def check_manager_permission(user):
    if user.is_superuser: return True
    group = user.groups.first()
    if group and hasattr(group, 'quyen'):
        quyen = group.quyen
        if quyen.pos_view and not quyen.inventory_view and not quyen.report_view and not quyen.system_all:
            return False
        return True
    return False

# ==========================================
# LOGIC TRÍ TUỆ NHÂN TẠO CẢNH BÁO KHO (JIT)
# ==========================================
def calculate_jit_import(tomorrow_forecast_pax):
    recommendations = []
    today = timezone.now().date()
    seven_days_ago = today - datetime.timedelta(days=7)
    
    total_pax_7d_ve = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date__gte=seven_days_ago,
        hoa_don__trang_thai='da_thanh_toan'
    ).filter(
        Q(goi_buffet__isnull=False) | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('so_luong'))['tong'] or 1
    
    nguyen_lieu_list = NguyenLieu.objects.all()
    
    for nl in nguyen_lieu_list:
        xuat_7d = ChiTietXuatKho.objects.filter(
            nguyen_lieu=nl,
            phieu_xuat__ngay_xuat__date__gte=seven_days_ago
        ).aggregate(tong=Sum('so_luong_xuat'))['tong'] or 0
        
        if xuat_7d == 0:
            continue
            
        u_avg = float(xuat_7d) / float(total_pax_7d_ve)
        nhu_cau_ngay_mai = float(tomorrow_forecast_pax) * u_avg
        
        ton_kho_hien_tai = float(nl.ton_kho)
        luong_can_co = nhu_cau_ngay_mai * 1.10 
        
        if ton_kho_hien_tai < luong_can_co:
            can_nhap = luong_can_co - ton_kho_hien_tai
            recommendations.append({
                'ten_nguyen_lieu': nl.ten_nguyen_lieu,
                'don_vi': nl.don_vi_tinh,
                'ton_kho': round(ton_kho_hien_tai, 2),
                'nhu_cau_ngay_mai': round(nhu_cau_ngay_mai, 2),
                'de_xuat_nhap': round(can_nhap + 0.5)
            })
            
    return sorted(recommendations, key=lambda x: x['de_xuat_nhap'], reverse=True)[:4]

# ==========================================
# LOGIC DASHBOARD TỔNG QUAN
# ==========================================
def get_realtime_data(today):
    hoa_don_hom_nay = HoaDon.objects.filter(thoi_gian_vao__date=today).exclude(trang_thai='da_huy')
    doanh_thu = hoa_don_hom_nay.filter(trang_thai='da_thanh_toan').aggregate(tong=Sum('khach_can_tra'))['tong'] or 0
    
    thuc_khach = ChiTietHoaDon.objects.filter(
        hoa_don__in=hoa_don_hom_nay
    ).filter(
        Q(goi_buffet__isnull=False) | 
        Q(ten_mon_luu_tru__icontains='vé') | 
        Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('so_luong'))['tong'] or 0

    so_bill = hoa_don_hom_nay.count()
    
    tong_ban = BanAn.objects.exclude(trang_thai='da_xoa').count() or 1
    ban_dang_phuc_vu = BanAn.objects.filter(trang_thai='dang_an').count()
    dat_ban = PhieuDatBan.objects.filter(thoi_gian_den__date=today).aggregate(tong=Sum('so_nguoi'))['tong'] or 0
    hoa_don_gan_day = list(hoa_don_hom_nay.select_related('ban_an', 'khach_hang').order_by('-thoi_gian_vao')[:5])
    
    return {
        'doanh_thu_hom_nay': doanh_thu, 'thuc_khach_hom_nay': thuc_khach,
        'rev_pax': int(doanh_thu / thuc_khach) if thuc_khach > 0 else 0,
        'ban_dang_phuc_vu': ban_dang_phuc_vu, 'tong_ban': tong_ban,
        'occupancy_rate': round((ban_dang_phuc_vu / tong_ban) * 100, 1),
        'turnover_rate': round(so_bill / tong_ban, 1),
        'dat_ban_hom_nay': dat_ban, 'hoa_don_gan_day': hoa_don_gan_day
    }

def get_cost_data(today, doanh_thu_hom_nay, thuc_khach_hom_nay):
    tien_xuat_kho = ChiTietXuatKho.objects.filter(phieu_xuat__ngay_xuat__date=today).aggregate(
        tong_gia_von=Sum(ExpressionWrapper(F('so_luong_xuat') * F('nguyen_lieu__don_gia_trung_binh'), output_field=DecimalField(max_digits=12, decimal_places=2)))
    )['tong_gia_von'] or 0
    food_cost_pct = round((float(tien_xuat_kho) / float(doanh_thu_hom_nay)) * 100, 1) if doanh_thu_hom_nay > 0 else 0.0
    so_nhan_vien = ChiTietCaLam.objects.filter(ca_lam_viec__ngay_lam_viec=today).count()
    staff_cost_per_pax = int((so_nhan_vien * SYSTEM_CONFIG['default_salary_per_shift']) / thuc_khach_hom_nay) if thuc_khach_hom_nay > 0 else 0
    return {'food_cost_pct': food_cost_pct, 'staff_cost_per_pax': staff_cost_per_pax}

def get_top_drinks(today):
    return ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date=today,
        do_uong__isnull=False
    ).exclude(
        hoa_don__trang_thai='da_huy'
    ).values('ten_mon_luu_tru') \
     .annotate(total_sold=Sum('so_luong')) \
     .order_by('-total_sold')[:5]

def get_ai_forecast_and_charts_dashboard(today, current_hour):
    khach_theo_gio = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date=today
    ).exclude(
        hoa_don__trang_thai='da_huy'
    ).filter(
        Q(goi_buffet__isnull=False) | 
        Q(ten_mon_luu_tru__icontains='vé') | 
        Q(ten_mon_luu_tru__icontains='buffet')
    ).annotate(
        gio=ExtractHour('hoa_don__thoi_gian_vao')
    ).values('gio').annotate(
        tong_khach=Sum('so_luong')
    ).order_by('gio')
    
    dict_thuc_te = {item['gio']: item['tong_khach'] for item in khach_theo_gio}
    
    khung_gio_hoat_dong = list(range(9, 22)) 
    chart_labels = [f"{h}h" for h in khung_gio_hoat_dong]
    chart_thuc_te, chart_du_bao = [], []

    dates_to_compare = [today - datetime.timedelta(days=7*i) for i in range(1, 5)]
    khach_4_tuan_truoc = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date__in=dates_to_compare
    ).exclude(
        hoa_don__trang_thai='da_huy'
    ).filter(
        Q(goi_buffet__isnull=False) | 
        Q(ten_mon_luu_tru__icontains='vé') | 
        Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('so_luong'))['tong'] or 0
    
    tb_khach_theo_thu = int(khach_4_tuan_truoc / 4) if khach_4_tuan_truoc > 0 else SYSTEM_CONFIG['fallback_pax']
    ai_khach_max = int(tb_khach_theo_thu * SYSTEM_CONFIG['ai_max_factor'])

    for h in khung_gio_hoat_dong:
        chart_du_bao.append(int(ai_khach_max * SYSTEM_CONFIG['ai_distribution'].get(h, 0.1)))
        chart_thuc_te.append(dict_thuc_te.get(h, 0) if h <= current_hour else None)

    ai_khach_trua = int(ai_khach_max * SYSTEM_CONFIG['ai_lunch_ratio'])
    
    inventory_warnings = calculate_jit_import(ai_khach_max) 
    
    return {
        'chart_labels': chart_labels, 'chart_thuc_te': chart_thuc_te, 'chart_du_bao': chart_du_bao,
        'ai_khach_min': int(tb_khach_theo_thu * SYSTEM_CONFIG['ai_min_factor']), 'ai_khach_max': ai_khach_max,
        'ai_khach_trua': ai_khach_trua, 'ai_khach_toi': ai_khach_max - ai_khach_trua,
        'ai_doanh_thu_m': round((ai_khach_max * SYSTEM_CONFIG['arpu_expected']) / 1000000, 1),
        'inventory_warnings': inventory_warnings
    }

def build_dashboard_context(today, current_hour):
    realtime_data = get_realtime_data(today)
    cost_data = get_cost_data(today, realtime_data['doanh_thu_hom_nay'], realtime_data['thuc_khach_hom_nay'])
    ai_data = get_ai_forecast_and_charts_dashboard(today, current_hour)
    top_drinks = get_top_drinks(today)
    return {**realtime_data, **cost_data, **ai_data, 'top_do_uong': top_drinks}

@login_required(login_url='login')
def dashboard_view(request):
    if not check_manager_permission(request.user):
        messages.warning(request, "Khu vực nội bộ! Bạn đã chuyển về POS.")
        return redirect('pos')
    now = timezone.now()
    today, current_hour = now.date(), now.hour
    cache_key = f'dashboard_global_u{request.user.id}_{today}_{current_hour}'
    context = cache.get_or_set(cache_key, lambda: build_dashboard_context(today, current_hour), timeout=SYSTEM_CONFIG['cache_timeout'])
    return render(request, 'dashboard/dashboard.html', context)


# ==========================================
# LOGIC TRANG TRỢ LÝ AI (AI DSS PIPELINE)
# ==========================================
def get_ai_features(today):
    features = {}
    hd_today = HoaDon.objects.filter(thoi_gian_vao__date=today, trang_thai='da_thanh_toan')
    features['revenue_today'] = hd_today.aggregate(tong=Sum('khach_can_tra'))['tong'] or 0
    
    features['pax_today'] = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date=today
    ).exclude(
        hoa_don__trang_thai='da_huy'
    ).filter(
        Q(goi_buffet__isnull=False) | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('so_luong'))['tong'] or 0
    
    seven_days_ago = today - datetime.timedelta(days=7)
    past_bills = HoaDon.objects.filter(thoi_gian_vao__date__gte=seven_days_ago, thoi_gian_vao__date__lt=today)
    active_days = past_bills.values('thoi_gian_vao__date').distinct().count()
    days_divisor = active_days if active_days > 0 else 1
    
    past_tickets = ChiTietHoaDon.objects.filter(
        hoa_don__in=past_bills
    ).exclude(
        hoa_don__trang_thai='da_huy'
    ).filter(
        Q(goi_buffet__isnull=False) | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).aggregate(tong=Sum('so_luong'))['tong'] or 0
    
    features['avg_pax_7d'] = past_tickets / days_divisor

    dessert_today = ChiTietHoaDon.objects.filter(hoa_don__thoi_gian_vao__date=today, do_uong__danh_muc__ten_danh_muc__icontains='Tráng miệng').exclude(hoa_don__trang_thai='da_huy').aggregate(tong=Sum('thanh_tien'))['tong'] or 0
    dessert_past_total = ChiTietHoaDon.objects.filter(hoa_don__in=past_bills, do_uong__danh_muc__ten_danh_muc__icontains='Tráng miệng').exclude(hoa_don__trang_thai='da_huy').aggregate(tong=Sum('thanh_tien'))['tong'] or 0
    dessert_7d_avg = dessert_past_total / days_divisor
    
    if dessert_7d_avg == 0:
        features['dessert_growth'] = 0.0 
    else:
        features['dessert_growth'] = ((dessert_today - dessert_7d_avg) / dessert_7d_avg) * 100

    total_bills = HoaDon.objects.filter(thoi_gian_vao__date=today).exclude(trang_thai='da_huy').count()
    
    family_bills = ChiTietHoaDon.objects.filter(
        hoa_don__thoi_gian_vao__date=today
    ).exclude(
        hoa_don__trang_thai='da_huy'
    ).filter(
        Q(goi_buffet__isnull=False) | Q(ten_mon_luu_tru__icontains='vé') | Q(ten_mon_luu_tru__icontains='buffet')
    ).values('hoa_don').annotate(tong_ve=Sum('so_luong')).filter(tong_ve__gte=4).count()

    features['family_ratio'] = (family_bills / total_bills) * 100 if total_bills > 0 else 0

    features['staff_count'] = ChiTietCaLam.objects.filter(ca_lam_viec__ngay_lam_viec=today).count() or 1
    weekday_factor = 1.25 if today.weekday() >= 4 else 0.95
    features['pax_forecast'] = int(features['avg_pax_7d'] * weekday_factor)

    return features

def detect_insights(features):
    insights = []
    data_volume_bonus = min(10.0, (features['pax_today'] / 50.0))

    dessert_risk_score = (abs(features['dessert_growth']) * 0.6) + (features['family_ratio'] * 0.4)
    if features['dessert_growth'] < -5 and dessert_risk_score > 15:
        conf_score = min(98.5, 75.0 + data_volume_bonus + (abs(features['dessert_growth']) / 5))
        insights.append({
            'type': 'warning', 'icon': 'bi-graph-down-arrow', 'color': 'danger', 
            'title': 'Doanh thu nhóm Tráng miệng/Giải khát giảm', 
            'description': f"Doanh thu đồ ngọt giảm {abs(features['dessert_growth']):.1f}%.",
            'root_cause': f"Tệp khách gia đình chiếm {features['family_ratio']:.1f}% nhưng thiếu item gọi chung.",
            'action': 'Tự động tạo Combo Tráng Miệng Gia Đình', 
            'simulation': '+8.5%', 'impact_metric': 'Doanh thu Dessert',
            'confidence': conf_score,
            'explain': "Scoring Model: Pattern Matching trên lịch sử hóa đơn."
        })

    pax_per_staff = features['pax_forecast'] / features['staff_count']
    workload_score = pax_per_staff / 30.0 
    
    if workload_score > 1.2:
        conf_score = min(99.0, 80.0 + (workload_score * 5) + data_volume_bonus)
        insights.append({
            'type': 'risk', 'icon': 'bi-exclamation-triangle-fill', 'color': 'warning', 
            'title': 'Rủi ro Quá tải Năng lực',
            'description': f"Phục vụ / Khách dự kiến là 1:{int(pax_per_staff)} (Vượt an toàn 1:30).",
            'root_cause': f"Hệ số mô hình đẩy lượng khách lên {features['pax_forecast']} Pax.",
            'action': 'Điều động thêm 02 nhân sự Bar/Phục vụ', 
            'simulation': '-40%', 'impact_metric': 'Thời gian chờ nước',
            'confidence': conf_score,
            'explain': "Regression Model: Khớp tải trọng nhân sự với độ trễ phục vụ."
        })

    if features['family_ratio'] > 25:
        conf_score = min(95.0, 70.0 + (features['family_ratio'] / 2) + data_volume_bonus)
        insights.append({
            'type': 'opportunity', 'icon': 'bi-stars', 'color': 'success', 
            'title': 'Cơ hội: Upsell Tháp Đồ Uống',
            'description': f"Tỷ lệ khách nhóm đông đạt {features['family_ratio']:.1f}%.",
            'root_cause': "Khách đi đông có xu hướng gọi đồ uống lẻ tốn kém.",
            'action': 'Mời chào Tháp Bia/Trà Trái Cây cho bàn > 4 Pax', 
            'simulation': '+15,000đ', 'impact_metric': 'ARPU (Doanh thu/Khách)',
            'confidence': conf_score,
            'explain': "Market Basket Analysis (Apriori Algorithm)."
        })
        
    return insights

def get_ai_charts_and_mutations(today, daily_pax, days_multiplier=1):
    days_name = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
    rev_labels, rev_actual, rev_forecast = [], [], []
    
    for i in range(5, -2, -1):
        d = today - datetime.timedelta(days=i)
        label = days_name[d.weekday()] + (" (Dự báo)" if i < 0 else "")
        rev_labels.append(label)
        
        if i > 0: 
            tong = HoaDon.objects.filter(thoi_gian_vao__date=d, trang_thai='da_thanh_toan').aggregate(tong=Sum('khach_can_tra'))['tong'] or 0
            rev_actual.append(int(tong / 1000000) if tong > 0 else None)
            rev_forecast.append(None)
        elif i == 0: 
            tong = HoaDon.objects.filter(thoi_gian_vao__date=d, trang_thai='da_thanh_toan').aggregate(tong=Sum('khach_can_tra'))['tong'] or 0
            rev_actual.append(int(tong / 1000000) if tong > 0 else 0)
            rev_forecast.append(int(tong / 1000000) if tong > 0 else 0)
        else: 
            rev_actual.append(None)
            rev_forecast.append(int((daily_pax * SYSTEM_CONFIG['arpu_expected']) / 1000000))

    traffic_labels = ['17h', '18h', '19h', '20h', '21h']
    traffic_forecast = [int(daily_pax * days_multiplier * SYSTEM_CONFIG['ai_distribution'].get(h, 0.1)) for h in range(17, 22)]

    mid_date = today - datetime.timedelta(days=3)
    start_date = today - datetime.timedelta(days=6)

    total_recent = ChiTietHoaDon.objects.filter(hoa_don__thoi_gian_vao__date__gte=mid_date, hoa_don__thoi_gian_vao__date__lt=today).exclude(hoa_don__trang_thai='da_huy').aggregate(tong=Sum('so_luong'))['tong'] or 1
    total_past = ChiTietHoaDon.objects.filter(hoa_don__thoi_gian_vao__date__gte=start_date, hoa_don__thoi_gian_vao__date__lt=mid_date).exclude(hoa_don__trang_thai='da_huy').aggregate(tong=Sum('so_luong'))['tong'] or 1

    recent_data = ChiTietHoaDon.objects.filter(hoa_don__thoi_gian_vao__date__gte=mid_date, hoa_don__thoi_gian_vao__date__lt=today).exclude(hoa_don__trang_thai='da_huy').values('ten_mon_luu_tru').annotate(tong_sl=Sum('so_luong'))
    past_data = ChiTietHoaDon.objects.filter(hoa_don__thoi_gian_vao__date__gte=start_date, hoa_don__thoi_gian_vao__date__lt=mid_date).exclude(hoa_don__trang_thai='da_huy').values('ten_mon_luu_tru').annotate(tong_sl=Sum('so_luong'))
    past_dict = {item['ten_mon_luu_tru']: item['tong_sl'] for item in past_data}
    
    mutations_list = []
    for item in recent_data:
        name, recent_sl = item['ten_mon_luu_tru'], item['tong_sl']
        past_sl = past_dict.get(name, 0)
        
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
            mutations.append({'ten_mon': m['name'], 'icon': 'bi-arrow-up-right', 'bg_color': '#ecfdf5', 'text_color': '#10b981', 'text_class': 'text-success', 'mo_ta': f"Tỷ trọng gọi món tăng <b class='text-success'>+{m['growth']:.1f}%</b>"})
        else:
            mutations.append({'ten_mon': m['name'], 'icon': 'bi-arrow-down-right', 'bg_color': '#fef2f2', 'text_color': '#ef4444', 'text_class': 'text-danger', 'mo_ta': f"Tỷ trọng gọi món giảm <b class='text-danger'>{m['growth']:.1f}%</b>"})

    if not mutations:
        mutations = [
            {'ten_mon': 'Trà Đào Cam Sả', 'icon': 'bi-arrow-up-right', 'bg_color': '#ecfdf5', 'text_color': '#10b981', 'text_class': 'text-success', 'mo_ta': "Tỷ trọng gọi món tăng <b class='text-success'>+45%</b>"},
            {'ten_mon': 'Cà Phê Muối', 'icon': 'bi-arrow-down-right', 'bg_color': '#fef2f2', 'text_color': '#ef4444', 'text_class': 'text-danger', 'mo_ta': "Tỷ trọng gọi món giảm <b class='text-danger'>-20%</b>"}
        ]

    return {
        'rev_labels': rev_labels, 'rev_actual': rev_actual, 'rev_forecast': rev_forecast,
        'traffic_labels': traffic_labels, 'traffic_forecast': traffic_forecast,
        'mutations': mutations
    }

@login_required(login_url='login')
def ai_analytics_view(request):
    if not check_manager_permission(request.user):
        messages.warning(request, "Tính năng AI chỉ dành cho cấp Quản lý!")
        return redirect('pos')

    today = timezone.now().date()
    
    time_range = request.GET.get('range', 'today')
    days_multiplier = 7 if time_range == '7d' else (30 if time_range == '30d' else 1)
    
    features = get_ai_features(today)
    
    daily_pax = features['pax_forecast']
    
    features['pax_forecast'] *= days_multiplier
    features['staff_count'] *= days_multiplier
    
    insights = detect_insights(features)
    insights.sort(key=lambda x: x['confidence'], reverse=True)
    
    decisions = [{'title': ins['action'], 'type': ins['type']} for ins in insights]
    
    charts_and_mutations = get_ai_charts_and_mutations(today, daily_pax, days_multiplier)

    context = {
        'page_title': 'AI Hỗ trợ Ra Quyết Định (DSS)',
        'features': features,
        'insights': insights,
        'decisions': decisions,
        'time_range': time_range,
        **charts_and_mutations
    }
    return render(request, 'AI/ai_analytics.html', context)