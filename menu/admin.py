from django.contrib import admin
from .models import ThucDon

@admin.register(ThucDon)
class ThucDonAdmin(admin.ModelAdmin):
    list_display = ('ten_mon', 'ma_sku', 'loai_mon', 'danh_muc', 'gia_ban', 'trang_thai')
    list_filter = ('loai_mon', 'danh_muc', 'trang_thai')
    search_fields = ('ten_mon', 'ma_sku')