# hr/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class NhanVien(models.Model):
    GIOI_TINH_CHOICES = [('Nam', 'Nam'), ('Nữ', 'Nữ'), ('Khác', 'Khác')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    ma_nv = models.CharField(max_length=20, unique=True)
    ho_ten = models.CharField(max_length=255)
    gioi_tinh = models.CharField(max_length=10, choices=GIOI_TINH_CHOICES, default='Nam')
    ngay_sinh = models.DateField(null=True, blank=True)
    so_dien_thoai = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    dia_chi = models.CharField(max_length=500, null=True, blank=True)
    chuc_vu = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.ma_nv} - {self.ho_ten}"

class CaLamViec(models.Model):
    SHIFT_CHOICES = [('morning', 'Ca Sáng'), ('evening', 'Ca Tối'), ('full', 'Full-time')]
    DEPT_CHOICES = [('kitchen', 'Bếp'), ('service', 'Phục vụ'), ('cashier', 'Thu ngân'), ('other', 'Khác')]
    
    ngay_lam_viec = models.DateField(default=timezone.now, verbose_name="Ngày làm việc")
    loai_ca = models.CharField(max_length=20, choices=SHIFT_CHOICES, default='morning')
    bo_phan = models.CharField(max_length=20, choices=DEPT_CHOICES, default='service')
    ghi_chu = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.get_loai_ca_display()} - {self.ngay_lam_viec}"

class ChiTietCaLam(models.Model):
    ca_lam_viec = models.ForeignKey(CaLamViec, on_delete=models.CASCADE, related_name='chi_tiet_ca')
    nhan_vien = models.ForeignKey(NhanVien, on_delete=models.CASCADE)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['ca_lam_viec', 'nhan_vien'], name='unique_nhan_vien_ca_lam')
        ]

class NgayNghi(models.Model):
    nhan_vien = models.ForeignKey(NhanVien, on_delete=models.CASCADE, related_name='ngay_nghi')
    ngay_nghi = models.DateField(verbose_name="Ngày xin nghỉ")
    ly_do = models.CharField(max_length=255, blank=True, null=True, verbose_name="Lý do nghỉ")
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['nhan_vien', 'ngay_nghi'], name='unique_ngay_nghi_nhan_vien')
        ]

    def __str__(self):
        return f"{self.nhan_vien.ho_ten} nghỉ ngày {self.ngay_nghi}"