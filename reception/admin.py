from django.contrib import admin
from .models import KhachHang, KhuVuc, BanAn, PhieuDatBan

@admin.register(KhachHang)
class KhachHangAdmin(admin.ModelAdmin):
    list_display = ('ho_ten', 'so_dien_thoai', 'diem_tich_luy')
    search_fields = ('ho_ten', 'so_dien_thoai')

@admin.register(KhuVuc)
class KhuVucAdmin(admin.ModelAdmin):
    list_display = ('ten_khu_vuc',)

@admin.register(BanAn)
class BanAnAdmin(admin.ModelAdmin):
    list_display = ('ten_ban', 'khu_vuc', 'so_ghe', 'trang_thai')
    list_filter = ('khu_vuc', 'trang_thai')

@admin.register(PhieuDatBan)
class PhieuDatBanAdmin(admin.ModelAdmin):
    list_display = ('khach_hang', 'ban', 'thoi_gian_den', 'so_nguoi', 'trang_thai')
    list_filter = ('trang_thai', 'thoi_gian_den')