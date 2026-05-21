# inventory/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class DanhMucNguyenLieu(models.Model):
    ten_danh_muc = models.CharField(max_length=255, verbose_name="Tên danh mục")
    ghi_chu = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.ten_danh_muc

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
    ma_nl = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="Mã NL")
    ten_nguyen_lieu = models.CharField(max_length=255, verbose_name="Tên Nguyên liệu")
    danh_muc = models.ForeignKey(DanhMucNguyenLieu, on_delete=models.SET_NULL, null=True, verbose_name="Danh mục")
    don_vi_tinh = models.CharField(max_length=50, default='Kg')
    # Đã chuyển về DecimalField để đồng bộ khi tính toán tiền nong, tránh sai số thập phân
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

class PhieuNhapKho(models.Model):
    ma_phieu = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nha_cung_cap = models.ForeignKey(NhaCungCap, on_delete=models.SET_NULL, null=True)
    nguoi_nhap = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    ngay_nhap = models.DateTimeField(default=timezone.now)
    tong_tien_nhap = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    da_thanh_toan = models.BooleanField(default=True)
    ghi_chu = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.ma_phieu or "Phiếu Nhập mới"

    def save(self, *args, **kwargs):
        if not self.ma_phieu:
            max_id = PhieuNhapKho.objects.aggregate(models.Max('id'))['id__max']
            new_id = (max_id or 0) + 1
            self.ma_phieu = f"PN-{str(new_id).zfill(5)}"
        super().save(*args, **kwargs)

class ChiTietNhapKho(models.Model):
    phieu_nhap = models.ForeignKey(PhieuNhapKho, on_delete=models.CASCADE, related_name='chi_tiet')
    nguyen_lieu = models.ForeignKey(NguyenLieu, on_delete=models.CASCADE)
    so_luong = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Số lượng nhập")
    don_gia = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Đơn giá nhập")
    thanh_tien = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.so_luong and self.don_gia:
            # Đã an toàn tuyệt đối, Decimal * Decimal
            self.thanh_tien = self.so_luong * self.don_gia
        super().save(*args, **kwargs)

class PhieuXuatKho(models.Model):
    ma_phieu = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nguoi_xuat = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    ly_do_xuat = models.CharField(max_length=255, default="Xuất cho Bếp chính")
    ngay_xuat = models.DateTimeField(default=timezone.now)
    ghi_chu = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.ma_phieu or "Phiếu Xuất mới"

    def save(self, *args, **kwargs):
        if not self.ma_phieu:
            max_id = PhieuXuatKho.objects.aggregate(models.Max('id'))['id__max']
            new_id = (max_id or 0) + 1
            self.ma_phieu = f"PX-{str(new_id).zfill(5)}"
        super().save(*args, **kwargs)

class ChiTietXuatKho(models.Model):
    phieu_xuat = models.ForeignKey(PhieuXuatKho, on_delete=models.CASCADE, related_name='chi_tiet')
    nguyen_lieu = models.ForeignKey(NguyenLieu, on_delete=models.CASCADE)
    so_luong_xuat = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Số lượng xuất")
    ghi_chu = models.CharField(max_length=255, blank=True, null=True)