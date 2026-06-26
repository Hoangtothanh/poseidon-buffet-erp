from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class NhaCungCap(models.Model):
    ten_ncc = models.CharField(max_length=255, verbose_name="Tên Nhà Cung Cấp")
    nguoi_lien_he = models.CharField(max_length=255, blank=True, null=True)
    trang_thai = models.BooleanField(default=True, verbose_name="Đang hợp tác")
    so_dien_thoai = models.CharField(max_length=20, blank=True, null=True)
    dia_chi = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    cong_no = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Công nợ (VNĐ)")

    def __str__(self):
        return self.ten_ncc

class NguyenLieu(models.Model):
    DANH_MUC_CHOICES = [
        ('hai_san', 'Hải Sản Tươi Sống'),
        ('thit', 'Thịt (Bò, Gà, Heo)'),
        ('rau_cu', 'Rau Củ Quả'),
        ('gia_vi', 'Gia Vị & Đồ Khô'),
        ('do_uong', 'Đồ Uống (Chai/Lon)'),
        ('khac', 'Khác'),
    ]

    ma_nl = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="Mã NL")
    ten_nguyen_lieu = models.CharField(max_length=255, verbose_name="Tên Nguyên liệu")
    danh_muc = models.CharField(max_length=50, choices=DANH_MUC_CHOICES, default='khac', verbose_name="Danh mục")
    don_vi_tinh = models.CharField(max_length=50, default='Kg')
    ton_kho = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Tồn kho hiện tại")
    muc_canh_bao = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, verbose_name="Mức tồn tối thiểu")
    don_gia_trung_binh = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Đơn giá TB")

    def __str__(self):
        return f"{self.ten_nguyen_lieu} ({self.don_vi_tinh})"

    def save(self, *args, **kwargs):
        if not self.ma_nl:
            max_id = NguyenLieu.objects.aggregate(models.Max('id'))['id__max']
            new_id = (max_id or 0) + 1
            self.ma_nl = f"NL-{str(new_id).zfill(3)}"
        super().save(*args, **kwargs)

class PhieuKho(models.Model):
    LOAI_PHIEU = [
        ('nhap', 'Phiếu Nhập Kho'),
        ('xuat', 'Phiếu Xuất Kho'),
    ]

    ma_phieu = models.CharField(max_length=50, unique=True, blank=True, null=True)
    loai_phieu = models.CharField(max_length=10, choices=LOAI_PHIEU, default='nhap')
    nha_cung_cap = models.ForeignKey(NhaCungCap, on_delete=models.SET_NULL, null=True, blank=True)
    nguoi_thuc_hien = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    ngay_thuc_hien = models.DateTimeField(default=timezone.now)
    tong_tien = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    da_thanh_toan = models.BooleanField(default=True) # Chỉ dùng cho phiếu nhập
    ghi_chu = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"[{self.get_loai_phieu_display()}] {self.ma_phieu}"

    def save(self, *args, **kwargs):
        if not self.ma_phieu:
            prefix = 'PN' if self.loai_phieu == 'nhap' else 'PX'
            max_id = PhieuKho.objects.aggregate(models.Max('id'))['id__max']
            new_id = (max_id or 0) + 1
            self.ma_phieu = f"{prefix}-{str(new_id).zfill(5)}"
        super().save(*args, **kwargs)

class ChiTietPhieuKho(models.Model):
    phieu = models.ForeignKey(PhieuKho, on_delete=models.CASCADE, related_name='chi_tiet')
    nguyen_lieu = models.ForeignKey(NguyenLieu, on_delete=models.CASCADE)
    so_luong = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Số lượng")
    don_gia = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Đơn giá (chỉ dùng cho Nhập)")
    thanh_tien = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    ghi_chu = models.CharField(max_length=255, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.phieu.loai_phieu == 'nhap' and self.so_luong and self.don_gia:
            self.thanh_tien = self.so_luong * self.don_gia
        super().save(*args, **kwargs)