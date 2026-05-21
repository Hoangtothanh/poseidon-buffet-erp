# reception/models.py
from django.db import models
from django.utils import timezone
from customers.models import KhachHang

class KhuVuc(models.Model):
    ten_khu_vuc = models.CharField(max_length=100, verbose_name="Khu vực (Tầng 1/VIP)")
    trang_thai = models.BooleanField(default=True, verbose_name="Đang hoạt động")

    def __str__(self):
        return self.ten_khu_vuc

class BanAn(models.Model):
    TRANG_THAI_CHOICES = [
        ('trong', 'Bàn Trống'),
        ('dang_an', 'Đang Phục Vụ'),
        ('da_dat', 'Đã Đặt Trước'),
        ('cho_thanh_toan', 'Chờ Thanh Toán')
    ]
    ten_ban = models.CharField(max_length=50, verbose_name="Tên/Số bàn")
    so_ghe = models.IntegerField(default=4, verbose_name="Số ghế")
    khu_vuc = models.ForeignKey(KhuVuc, on_delete=models.CASCADE, related_name='danh_sach_ban')
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI_CHOICES, default='trong')

    def __str__(self):
        return f"{self.ten_ban} ({self.khu_vuc.ten_khu_vuc})"

class PhieuDatBan(models.Model):
    STATUS_CHOICES = [
        ('cho_xac_nhan', 'Chờ xác nhận'),
        ('da_xac_nhan', 'Đã xác nhận'),
        ('hoan_thanh', 'Đã check-in'),
        ('huy', 'Đã hủy'),
    ]
    khach_hang = models.ForeignKey(KhachHang, on_delete=models.CASCADE, related_name='lich_su_dat_ban')
    ban = models.ForeignKey(BanAn, on_delete=models.SET_NULL, null=True, blank=True, related_name='phieu_dat_ban')
    thoi_gian_den = models.DateTimeField(verbose_name="Thời gian khách đến")
    so_nguoi = models.IntegerField(default=1, verbose_name="Số người lớn")
    so_tre_em = models.IntegerField(default=0, verbose_name="Số trẻ em")
    trang_thai = models.CharField(max_length=20, choices=STATUS_CHOICES, default='cho_xac_nhan')
    ghi_chu = models.TextField(blank=True, null=True)
    thoi_gian_tao = models.DateTimeField(auto_now_add=True, null=True, verbose_name="Lúc đặt")

    def __str__(self):
        return f"Booking: {self.khach_hang.ho_ten} - {self.thoi_gian_den.strftime('%H:%M %d/%m')}"

class PhienSuDungBan(models.Model):
    STATUS_CHOICES = [
        ('dang_phuc_vu', 'Đang phục vụ'),
        ('da_thanh_toan', 'Đã thanh toán'),
        ('huy', 'Đã hủy (Khách bỏ về)'),
    ]
    ban = models.ForeignKey(BanAn, on_delete=models.CASCADE, related_name='cac_phien')
    khach_hang = models.ForeignKey(KhachHang, on_delete=models.SET_NULL, null=True, blank=True)
    phieu_dat = models.OneToOneField(PhieuDatBan, on_delete=models.SET_NULL, null=True, blank=True)
    
    thoi_gian_vao = models.DateTimeField(default=timezone.now, verbose_name="Giờ Check-in")
    thoi_gian_ra = models.DateTimeField(null=True, blank=True, verbose_name="Giờ Check-out")
    
    so_khach_thuc_te = models.IntegerField(default=1)
    trang_thai = models.CharField(max_length=20, choices=STATUS_CHOICES, default='dang_phuc_vu')
    ghi_chu = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Session #{self.id} - {self.ban.ten_ban} ({self.trang_thai})"