from django.contrib import admin
from .models import NhaCungCap, NguyenLieu, PhieuKho, ChiTietPhieuKho

@admin.register(NhaCungCap)
class NhaCungCapAdmin(admin.ModelAdmin):
    list_display = ('ten_ncc', 'so_dien_thoai', 'cong_no', 'trang_thai')
    list_filter = ('trang_thai',)

@admin.register(NguyenLieu)
class NguyenLieuAdmin(admin.ModelAdmin):
    list_display = ('ma_nl', 'ten_nguyen_lieu', 'danh_muc', 'ton_kho', 'don_vi_tinh')
    list_filter = ('danh_muc',)

class ChiTietPhieuKhoInline(admin.TabularInline):
    model = ChiTietPhieuKho
    extra = 1

@admin.register(PhieuKho)
class PhieuKhoAdmin(admin.ModelAdmin):
    list_display = ('ma_phieu', 'loai_phieu', 'ngay_thuc_hien', 'tong_tien')
    list_filter = ('loai_phieu',)
    inlines = [ChiTietPhieuKhoInline]