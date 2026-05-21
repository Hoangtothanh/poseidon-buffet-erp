# customers/models.py
from django.db import models
from django.utils import timezone

# ===== MODEL KHÁCH HÀNG =====
class KhachHang(models.Model):
    ho_ten = models.CharField(max_length=255, verbose_name="Tên khách hàng")
    so_dien_thoai = models.CharField(max_length=20, unique=True, verbose_name="Số điện thoại")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    ngay_sinh = models.DateField(blank=True, null=True, verbose_name="Ngày sinh")
    diem_tich_luy = models.IntegerField(default=0, verbose_name="Điểm thành viên")
    is_active = models.BooleanField(default=True, verbose_name="Trạng thái (Khóa/Mở)")
    ngay_tao = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Ngày tạo")

    def __str__(self):
        return f"{self.ho_ten} - {self.so_dien_thoai}"

    @property
    def hang_the(self):
        if self.diem_tich_luy >= 1500:  # Sửa lại thành 1500
            return 'kim cương'
        elif self.diem_tich_luy >= 500:   # Sửa lại thành 500
            return 'vàng'
        elif self.diem_tich_luy >= 200:
            return 'bạc'
        return 'thành viên'

# ===== MODEL MÃ KHUYẾN MÃI (VOUCHER) =====
class Voucher(models.Model):
    ma_code = models.CharField(max_length=50, unique=True, verbose_name="Mã Code")
    muc_giam = models.CharField(max_length=50, verbose_name="Mức giảm (vd: 15% hoặc 200000)")
    dieu_kien_toi_thieu = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Điều kiện hóa đơn")
    ngay_het_han = models.DateField(verbose_name="Ngày hết hạn")
    trang_thai = models.BooleanField(default=True, verbose_name="Trạng thái kích hoạt")
    ai_de_xuat = models.BooleanField(default=False, verbose_name="Do AI đề xuất") 
    
    ngay_tao = models.DateTimeField(auto_now_add=True)
    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.ma_code
        
    @property
    def da_het_han(self):
        """Kiểm tra xem voucher đã quá hạn so với hôm nay chưa"""
        return timezone.now().date() > self.ngay_het_han