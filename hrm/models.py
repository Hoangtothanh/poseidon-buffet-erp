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
    anh_dai_dien = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.ma_nv} - {self.ho_ten}"

class CaLamViec(models.Model):
    SHIFT_CHOICES = [('morning', 'Ca Sáng'), ('evening', 'Ca Tối'), ('full', 'Full-time'), ('nghi_phep', 'Xin nghỉ')]
    DEPT_CHOICES = [('kitchen', 'Bếp'), ('service', 'Phục vụ'), ('cashier', 'Thu ngân'), ('other', 'Khác')]
    
    ngay_lam_viec = models.DateField(default=timezone.now, verbose_name="Ngày làm việc/Xin nghỉ")
    loai_ca = models.CharField(max_length=20, choices=SHIFT_CHOICES, default='morning')
    bo_phan = models.CharField(max_length=20, choices=DEPT_CHOICES, default='service')
    ghi_chu = models.CharField(max_length=255, blank=True, null=True)
    nhan_vien = models.ManyToManyField('NhanVien', related_name='ca_lam_viec', blank=True)

    def __str__(self):
        return f"{self.get_loai_ca_display()} - {self.ngay_lam_viec}"

# Đã gộp ChiTietCaLam và NgayNghi vào model CaLamViec (Extreme Refactoring)