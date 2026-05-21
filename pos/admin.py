from django.contrib import admin
from .models import HoaDon, ChiTietHoaDon, ThanhToan

# ==========================================
# GIAO DIỆN INLINE (HIỂN THỊ CHI TIẾT TRONG HÓA ĐƠN)
# ==========================================
class ChiTietHoaDonInline(admin.TabularInline):
    model = ChiTietHoaDon
    extra = 1  # Hiển thị sẵn 1 dòng trống để thêm món nhanh
    fields = ('goi_buffet', 'do_uong', 'ten_mon_luu_tru', 'don_gia_luu_tru', 'so_luong', 'thanh_tien', 'ghi_chu_bep')

class ThanhToanInline(admin.TabularInline):
    model = ThanhToan
    extra = 0
    fields = ('phuong_thuc', 'so_tien_thu', 'ma_giao_dich_ngan_hang', 'nhan_vien_thu', 'thoi_gian_thu')
    readonly_fields = ('thoi_gian_thu',)


# ==========================================
# ĐĂNG KÝ CÁC BẢNG LÊN GIAO DIỆN ADMIN
# ==========================================
@admin.register(HoaDon)
class HoaDonAdmin(admin.ModelAdmin):
    list_display = ('ma_hoa_don', 'ban_an', 'khach_hang', 'tong_tien_hang', 'khach_can_tra', 'trang_thai', 'thoi_gian_vao')
    list_filter = ('trang_thai', 'thoi_gian_vao')
    search_fields = ('ma_hoa_don', 'khach_hang__ho_ten', 'khach_hang__so_dien_thoai', 'ban_an__ten_ban')
    inlines = [ChiTietHoaDonInline, ThanhToanInline] # Gắn 2 bảng con vào trong Hóa đơn
    readonly_fields = ('thoi_gian_vao', 'thoi_gian_ra')

@admin.register(ChiTietHoaDon)
class ChiTietHoaDonAdmin(admin.ModelAdmin):
    list_display = ('hoa_don', 'ten_mon_luu_tru', 'so_luong', 'don_gia_luu_tru', 'thanh_tien', 'thoi_gian_order')
    search_fields = ('hoa_don__ma_hoa_don', 'ten_mon_luu_tru')
    list_filter = ('thoi_gian_order',)

@admin.register(ThanhToan)
class ThanhToanAdmin(admin.ModelAdmin):
    list_display = ('hoa_don', 'phuong_thuc', 'so_tien_thu', 'nhan_vien_thu', 'thoi_gian_thu')
    list_filter = ('phuong_thuc', 'thoi_gian_thu')
    search_fields = ('hoa_don__ma_hoa_don', 'ma_giao_dich_ngan_hang')