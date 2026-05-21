from django.db import models
from django.contrib.auth.models import User
from customers.models import KhachHang
from reception.models import BanAn, PhienSuDungBan
from menu.models import GoiBuffet, DoUongDichVu

class HoaDon(models.Model):
    STATUS_CHOICES = [
        ('dang_phuc_vu', 'Đang phục vụ'),
        ('cho_thanh_toan', 'Chờ thanh toán'), # <-- THÊM MỚI: Dành cho lúc In Bill Tạm Tính
        ('da_thanh_toan', 'Đã thanh toán'),
        ('da_huy', 'Đã hủy'),
    ]
    ma_hoa_don = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="Mã Hóa Đơn")    
    ma_voucher = models.CharField(max_length=50, blank=True, null=True)
    tien_giam_voucher = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0
    )
    # LIÊN KẾT DỮ LIỆU
    phien_su_dung = models.OneToOneField(PhienSuDungBan, on_delete=models.SET_NULL, null=True, blank=True, related_name='hoa_don')
    ban_an = models.ForeignKey(BanAn, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Bàn ăn") # Cho phép Null nếu khách mua Takeaway
    khach_hang = models.ForeignKey(KhachHang, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Khách hàng")
    nhan_vien = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Thu ngân")
    
    # THỜI GIAN
    thoi_gian_vao = models.DateTimeField(auto_now_add=True, verbose_name="Giờ khách vào")
    thoi_gian_ra = models.DateTimeField(null=True, blank=True, verbose_name="Giờ in bill/Ra")
    
    # TÀI CHÍNH & SỐ LƯỢNG
    so_khach = models.IntegerField(default=1, verbose_name="Số lượng khách")
    tong_tien_hang = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Tổng tiền hàng")
    chiet_khau = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Giảm giá / Voucher")
    vat_phu_thu = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="VAT & Phụ thu khác")
    khach_can_tra = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Khách cần trả")
    
    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú hóa đơn")
    trang_thai = models.CharField(max_length=20, choices=STATUS_CHOICES, default='dang_phuc_vu')

    def __str__(self):
        ten_ban = self.ban_an.ten_ban if self.ban_an else 'Mang đi'
        return f"{self.ma_hoa_don or 'NEW'} - {ten_ban}"

    def save(self, *args, **kwargs):
        # TẠO MÃ HÓA ĐƠN AN TOÀN (Chống lỗi khi Database rỗng hoặc bị xóa record)
        if not self.ma_hoa_don:
            max_id = HoaDon.objects.aggregate(models.Max('id'))['id__max']
            new_id = (max_id or 0) + 1
            self.ma_hoa_don = f"INV-{str(new_id).zfill(5)}"
            
        super().save(*args, **kwargs)


class ChiTietHoaDon(models.Model):
    hoa_don = models.ForeignKey(HoaDon, on_delete=models.CASCADE, related_name='chi_tiet', verbose_name="Thuộc Hóa Đơn")
    
    # Thiết kế Mutually Exclusive (Chỉ 1 trong 2 có giá trị)
    goi_buffet = models.ForeignKey(GoiBuffet, on_delete=models.SET_NULL, null=True, blank=True)
    do_uong = models.ForeignKey(DoUongDichVu, on_delete=models.SET_NULL, null=True, blank=True)
    
    ten_mon_luu_tru = models.CharField(max_length=255, verbose_name="Tên món (Snapshot)")
    don_gia_luu_tru = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Đơn giá (Snapshot)")
    so_luong = models.IntegerField(default=1, verbose_name="Số lượng")
    thanh_tien = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Thành tiền")
    
    thoi_gian_order = models.DateTimeField(auto_now_add=True)
    
    # <-- ĐÃ SỬA: Đổi từ ghi_chu_bep thành ghi_chu để khớp với Frontend Javascript
    ghi_chu = models.CharField(max_length=255, blank=True, null=True, verbose_name="Ghi chú (Ít đá, không cay...)")

    def __str__(self):
        return f"{self.so_luong}x {self.ten_mon_luu_tru} ({self.hoa_don.ma_hoa_don})"

    def save(self, *args, **kwargs):
        if self.don_gia_luu_tru and self.so_luong:
            self.thanh_tien = self.don_gia_luu_tru * self.so_luong
        super().save(*args, **kwargs)


class ThanhToan(models.Model):
    PAYMENT_METHODS = [
        ('tien_mat', 'Tiền mặt (Cash)'),
        ('chuyen_khoan', 'Chuyển khoản (Bank Transfer)'),
        ('quet_the', 'Quẹt thẻ (POS / Credit)'),
    ]
    hoa_don = models.ForeignKey(HoaDon, on_delete=models.CASCADE, related_name='thanh_toan', verbose_name="Thuộc Hóa Đơn")
    phuong_thuc = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='tien_mat', verbose_name="Phương thức TT")
    so_tien_thu = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Số tiền đã thu")
    thoi_gian_thu = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian giao dịch")
    ma_giao_dich_ngan_hang = models.CharField(max_length=100, blank=True, null=True, verbose_name="Mã giao dịch")
    nhan_vien_thu = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Người thu tiền")

    def __str__(self):
        return f"{self.get_phuong_thuc_display()} - {self.so_tien_thu} ({self.hoa_don.ma_hoa_don})"