from django.contrib import admin
from .models import CaLamViec, NhanVien, ChiTietCaLam

# ==========================================
# 1. ADMIN CHO NHÂN VIÊN
# ==========================================
@admin.register(NhanVien)
class NhanVienAdmin(admin.ModelAdmin):
    list_display = ('ma_nv', 'ho_ten', 'gioi_tinh', 'chuc_vu', 'so_dien_thoai') 
    search_fields = ('ma_nv', 'ho_ten', 'so_dien_thoai')
    list_filter = ('gioi_tinh', 'chuc_vu')
    
# ==========================================
# 2. ADMIN CHO CA LÀM VIỆC
# ==========================================
# BƯỚC A: Phải khai báo Inline trước
class ChiTietCaLamInline(admin.TabularInline):
    model = ChiTietCaLam
    extra = 1 # Hiển thị sẵn 1 dòng trống để thêm nhân viên

# BƯỚC B: Mới khai báo Admin cho CaLamViec
@admin.register(CaLamViec)
class CaLamViecAdmin(admin.ModelAdmin):
    list_display = ('ngay_lam_viec', 'loai_ca', 'bo_phan', 'ghi_chu')
    list_filter = ('ngay_lam_viec', 'loai_ca', 'bo_phan')
    inlines = [ChiTietCaLamInline] # Nhúng Inline vào đây

# ==========================================
# 3. ADMIN CHO CHI TIẾT CA LÀM (TÙY CHỌN)
# ==========================================
@admin.register(ChiTietCaLam)
class ChiTietCaLamAdmin(admin.ModelAdmin):
    list_display = ('ca_lam_viec', 'nhan_vien')
    list_filter = ('ca_lam_viec__ngay_lam_viec', 'ca_lam_viec__bo_phan')
    search_fields = ('nhan_vien__ho_ten',)