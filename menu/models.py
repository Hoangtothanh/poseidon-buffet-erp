# menu/models.py
from django.db import models

class GoiBuffet(models.Model):
    ten_goi = models.CharField(max_length=255, verbose_name="Tên Gói Buffet")
    mo_ta = models.TextField(blank=True, null=True, verbose_name="Mô tả / Ghi chú")
    gia_ban = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá Bán (VNĐ)")
    gio_bat_dau = models.TimeField(blank=True, null=True, verbose_name="Giờ bắt đầu")
    gio_ket_thuc = models.TimeField(blank=True, null=True, verbose_name="Giờ kết thúc")
    ngay_ap_dung = models.CharField(max_length=50, blank=True, null=True, verbose_name="Ngày áp dụng (T2-CN)")
    trang_thai = models.BooleanField(default=True, verbose_name="Đang áp dụng")
    ngay_tao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ten_goi} - {self.gia_ban}đ"

class NgayLe(models.Model):
    ten_ngay_le = models.CharField(max_length=255, verbose_name="Tên Ngày Lễ")
    ngay = models.DateField(verbose_name="Ngày Lễ")

    def __str__(self):
        return f"{self.ten_ngay_le} ({self.ngay})"


class DanhMuc(models.Model):
    ten_danh_muc = models.CharField(max_length=255, unique=True, verbose_name="Tên Danh Mục")
    mo_ta = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, default='bi-cup-straw')
    trang_thai = models.BooleanField(default=True, verbose_name="Hiển thị POS")

    def __str__(self):
        return self.ten_danh_muc

class DoUongDichVu(models.Model):
    ten_mon = models.CharField(max_length=255, verbose_name="Tên Món / Phụ thu")
    ma_sku = models.CharField(max_length=50, blank=True, null=True, verbose_name="Mã SKU")
    danh_muc = models.ForeignKey('DanhMuc', on_delete=models.SET_NULL, null=True, blank=True, related_name='danh_sach_item')
    
    gia_ban = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Giá Bán / Phí")
    gia_von = models.DecimalField(max_digits=10, decimal_places=0, default=0, blank=True, null=True, verbose_name="Giá Vốn")
    hinh_anh = models.ImageField(upload_to='beverages/', blank=True, null=True)
    con_hang = models.BooleanField(default=True, verbose_name="Còn hàng")
    hien_thi_pos = models.BooleanField(default=True, verbose_name="Hiển thị POS")
    ngay_tao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ten_mon} ({self.gia_ban}đ)"

    def save(self, *args, **kwargs):
        if not self.ma_sku:
            prefix = 'BEV'
            if self.danh_muc and ('phụ thu' in self.danh_muc.ten_danh_muc.lower() or 'phí' in self.danh_muc.ten_danh_muc.lower()):
                prefix = 'FEE'
            max_id = DoUongDichVu.objects.aggregate(models.Max('id'))['id__max']
            new_id = (max_id or 0) + 1
            self.ma_sku = f"{prefix}-{str(new_id).zfill(4)}"
        super().save(*args, **kwargs)