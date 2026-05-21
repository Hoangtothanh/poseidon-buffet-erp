from django.contrib import admin
from .models import GoiBuffet, NgayLe, DanhMuc, DoUongDichVu

# ==========================================
# 1. GÓI BUFFET & NGÀY LỄ
# ==========================================
@admin.register(GoiBuffet)
class GoiBuffetAdmin(admin.ModelAdmin):
    list_display = ('ten_goi', 'gia_ban', 'gio_bat_dau', 'gio_ket_thuc', 'trang_thai')
    list_filter = ('trang_thai',)
    search_fields = ('ten_goi', 'mo_ta')

@admin.register(NgayLe)
class NgayLeAdmin(admin.ModelAdmin):
    list_display = ('ten_ngay_le', 'ngay')
    search_fields = ('ten_ngay_le',)


# ==========================================
# 2 DANH MỤC
# ==========================================
@admin.register(DanhMuc)
class DanhMucAdmin(admin.ModelAdmin):
    list_display = ('ten_danh_muc', 'icon', 'trang_thai')
    list_filter = ('trang_thai',)
    search_fields = ('ten_danh_muc',)


# ==========================================
# 3. ĐỒ UỐNG ALACARTE
# ==========================================
@admin.register(DoUongDichVu)
class DoUongDichVuAdmin(admin.ModelAdmin):
    list_display = ('ten_mon', 'ma_sku', 'danh_muc', 'gia_ban', 'con_hang', 'hien_thi_pos')
    list_filter = ('danh_muc', 'con_hang', 'hien_thi_pos')
    search_fields = ('ten_mon', 'ma_sku')