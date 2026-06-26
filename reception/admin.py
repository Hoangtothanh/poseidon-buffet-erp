from django.contrib import admin
from .models import BanAn, PhieuDatBan

@admin.register(BanAn)
class BanAnAdmin(admin.ModelAdmin):
    list_display = ('ten_ban', 'khu_vuc', 'so_ghe', 'trang_thai')
    list_filter = ('khu_vuc', 'trang_thai')

@admin.register(PhieuDatBan)
class PhieuDatBanAdmin(admin.ModelAdmin):
    list_display = ('khach_hang', 'ban', 'thoi_gian_den', 'so_nguoi', 'trang_thai')
    list_filter = ('trang_thai', 'thoi_gian_den')