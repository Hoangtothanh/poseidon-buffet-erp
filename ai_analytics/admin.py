from django.contrib import admin
from .models import AIEngineLog, AIDuDoanTieuThu, AIPhanTichThucDon, AIDuDoanLuuLuong

# 1. Nhật ký AI
@admin.register(AIEngineLog)
class AIEngineLogAdmin(admin.ModelAdmin):
    list_display = ('module_name', 'do_chinh_xac', 'lan_chay_cuoi', 'trang_thai')
    list_filter = ('module_name', 'trang_thai')
    search_fields = ('module_name',)

# 2. AI Dự đoán tiêu thụ nguyên liệu
@admin.register(AIDuDoanTieuThu)
class AIDuDoanTieuThuAdmin(admin.ModelAdmin):
    list_display = ('ten_mon', 'ngay_du_doan', 'nhom_mon', 'ai_du_doan_tieu_thu', 'xu_huong', 'bien_dong_phan_tram')
    list_filter = ('xu_huong', 'nhom_mon', 'ngay_du_doan')
    search_fields = ('ten_mon', 'nhom_mon')
    list_editable = ('xu_huong',)

# 3. AI Tối ưu thực đơn (Ma trận BCG)
@admin.register(AIPhanTichThucDon)
class AIPhanTichThucDonAdmin(admin.ModelAdmin):
    list_display = ('ten_mon', 'phan_loai_bcg', 'nhom_mon', 'ty_suat_loi_nhuan', 'do_pho_bien', 'food_cost')
    list_filter = ('phan_loai_bcg', 'nhom_mon')
    search_fields = ('ten_mon',)
    list_editable = ('phan_loai_bcg',)

# 4. AI Dự đoán lưu lượng khách
@admin.register(AIDuDoanLuuLuong)
class AIDuDoanLuuLuongAdmin(admin.ModelAdmin):
    list_display = (
        'ngay_du_doan',       # STT2 - Ngày dự đoán (tương lai)
        'ca_lam_viec',        # STT3 - Ca làm việc
        'khach_thuc_te',      # STT4 - Khách thực tế (update sau)
        'ai_du_doan_khach',   # STT5 - AI dự đoán
        'ty_le_lap_day',      # STT6 - Tỷ lệ lấp đầy (%)
        'trang_thai',         # STT7 - Phân loại cảnh báo
        'doanh_thu_ky_vong',  # STT8 - Doanh thu kỳ vọng
        'is_holiday',         # Yếu tố ngoại cảnh
    )
    list_filter = ('trang_thai', 'ca_lam_viec', 'is_holiday', 'ngay_du_doan')
    list_editable = ('trang_thai', 'khach_thuc_te')
    search_fields = ('ten_su_kien', 'loi_khuyen_van_hanh')
    readonly_fields = ('loi_khuyen_van_hanh',)
    date_hierarchy = 'ngay_du_doan'