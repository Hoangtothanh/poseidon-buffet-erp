from django.contrib import admin
from .models import DanhMucNguyenLieu, NhaCungCap, NguyenLieu, PhieuNhapKho, ChiTietNhapKho, PhieuXuatKho, ChiTietXuatKho

# Hiển thị Chi tiết Nhập ngay bên trong Phiếu Nhập
class ChiTietNhapKhoInline(admin.TabularInline):
    model = ChiTietNhapKho
    extra = 1

class ChiTietXuatKhoInline(admin.TabularInline):
    model = ChiTietXuatKho
    extra = 1

@admin.register(NguyenLieu)
class NguyenLieuAdmin(admin.ModelAdmin):
    list_display = ('ma_nl', 'ten_nguyen_lieu', 'danh_muc', 'ton_kho', 'don_vi_tinh', 'muc_canh_bao')
    list_filter = ('danh_muc',)
    search_fields = ('ten_nguyen_lieu', 'ma_nl')

@admin.register(PhieuNhapKho)
class PhieuNhapKhoAdmin(admin.ModelAdmin):
    list_display = ('ma_phieu', 'nha_cung_cap', 'ngay_nhap', 'tong_tien_nhap', 'nguoi_nhap')
    inlines = [ChiTietNhapKhoInline]

@admin.register(PhieuXuatKho)
class PhieuXuatKhoAdmin(admin.ModelAdmin):
    list_display = ('ma_phieu', 'ly_do_xuat', 'ngay_xuat', 'nguoi_xuat')
    inlines = [ChiTietXuatKhoInline]

admin.site.register(DanhMucNguyenLieu)
admin.site.register(NhaCungCap)