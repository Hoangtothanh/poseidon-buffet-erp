from django.contrib import admin
from .models import HoaDon, ChiTietHoaDon

class ChiTietHoaDonInline(admin.TabularInline):
    model = ChiTietHoaDon
    extra = 1

@admin.register(HoaDon)
class HoaDonAdmin(admin.ModelAdmin):
    list_display = ('ma_hoa_don', 'ban_an', 'khach_hang', 'tong_tien_hang', 'khach_can_tra', 'trang_thai', 'phuong_thuc_tt')
    list_filter = ('trang_thai', 'phuong_thuc_tt')
    inlines = [ChiTietHoaDonInline]