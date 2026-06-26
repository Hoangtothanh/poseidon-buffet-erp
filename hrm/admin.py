from django.contrib import admin
from .models import CaLamViec, NhanVien

@admin.register(NhanVien)
class NhanVienAdmin(admin.ModelAdmin):
    list_display = ('ma_nv', 'ho_ten', 'gioi_tinh', 'chuc_vu', 'so_dien_thoai') 
    search_fields = ('ma_nv', 'ho_ten', 'so_dien_thoai')
    list_filter = ('gioi_tinh', 'chuc_vu')
    
@admin.register(CaLamViec)
class CaLamViecAdmin(admin.ModelAdmin):
    list_display = ('ngay_lam_viec', 'loai_ca', 'bo_phan', 'ghi_chu')
    list_filter = ('ngay_lam_viec', 'loai_ca', 'bo_phan')
    filter_horizontal = ('nhan_vien',)