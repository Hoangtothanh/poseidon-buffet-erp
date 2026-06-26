# menu/models.py
from django.db import models

class ThucDon(models.Model):
    LOAI_CHOICES = [
        ('goi_buffet', 'Gói Buffet'),
        ('do_uong', 'Đồ Uống'),
        ('dich_vu', 'Dịch vụ Phụ thu'),
    ]
    DANH_MUC_CHOICES = [
        ('buffet', 'Buffet'),
        ('nuoc_ngot', 'Nước Ngọt'),
        ('bia_ruou', 'Bia & Rượu'),
        ('hai_san', 'Hải Sản Gọi Thêm'),
        ('phu_thu', 'Phụ Thu Dịch Vụ'),
    ]
    
    ten_mon = models.CharField(max_length=255, verbose_name="Tên Món / Gói")
    loai_mon = models.CharField(max_length=20, choices=LOAI_CHOICES, default='do_uong')
    danh_muc = models.CharField(max_length=50, choices=DANH_MUC_CHOICES, default='nuoc_ngot')
    mo_ta = models.TextField(blank=True, null=True, verbose_name="Mô tả / Ghi chú")
    ma_sku = models.CharField(max_length=50, blank=True, null=True, verbose_name="Mã SKU")
    
    gia_ban = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="Giá Bán (VNĐ)")
    gia_von = models.DecimalField(max_digits=10, decimal_places=0, default=0, blank=True, null=True, verbose_name="Giá Vốn")
    hinh_anh = models.ImageField(upload_to='menu/', blank=True, null=True)
    
    # Chỉ dành riêng cho loại gói Buffet
    gio_bat_dau = models.TimeField(blank=True, null=True, verbose_name="Giờ bắt đầu")
    gio_ket_thuc = models.TimeField(blank=True, null=True, verbose_name="Giờ kết thúc")
    
    ap_dung_t2 = models.BooleanField(default=True, verbose_name="Thứ 2")
    ap_dung_t3 = models.BooleanField(default=True, verbose_name="Thứ 3")
    ap_dung_t4 = models.BooleanField(default=True, verbose_name="Thứ 4")
    ap_dung_t5 = models.BooleanField(default=True, verbose_name="Thứ 5")
    ap_dung_t6 = models.BooleanField(default=True, verbose_name="Thứ 6")
    ap_dung_t7 = models.BooleanField(default=True, verbose_name="Thứ 7")
    ap_dung_cn = models.BooleanField(default=True, verbose_name="Chủ Nhật")
    
    trang_thai = models.BooleanField(default=True, verbose_name="Hiển thị trên POS")
    ngay_tao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_loai_mon_display()}] {self.ten_mon} - {self.gia_ban}đ"

    def save(self, *args, **kwargs):
        if not self.ma_sku:
            prefix = 'MNU'
            if self.loai_mon == 'goi_buffet': prefix = 'BUF'
            elif self.loai_mon == 'dich_vu': prefix = 'SRV'
            max_id = ThucDon.objects.aggregate(models.Max('id'))['id__max']
            new_id = (max_id or 0) + 1
            self.ma_sku = f"{prefix}-{str(new_id).zfill(4)}"
        super().save(*args, **kwargs)