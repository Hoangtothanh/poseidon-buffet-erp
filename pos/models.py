from django.db import models
from django.contrib.auth.models import User
from customers.models import KhachHang
from reception.models import BanAn
from menu.models import ThucDon

class HoaDon(models.Model):
    STATUS_CHOICES = [
        ('dang_phuc_vu', 'Đang phục vụ'),
        ('cho_thanh_toan', 'Chờ thanh toán'), 
        ('da_thanh_toan', 'Đã thanh toán'),
        ('da_huy', 'Đã hủy'),
    ]
    PAYMENT_METHODS = [
        ('tien_mat', 'Tiền mặt (Cash)'),
        ('chuyen_khoan', 'Chuyển khoản (Bank Transfer)'),
    ]

    ma_hoa_don = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="Mã Hóa Đơn")    
    
    # LIÊN KẾT DỮ LIỆU
    ban_an = models.ForeignKey(BanAn, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Bàn ăn") 
    khach_hang = models.ForeignKey(KhachHang, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Khách hàng")
    nhan_vien = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Thu ngân")
    
    # THỜI GIAN VÒNG ĐỜI (Thay thế PhienSuDungBan)
    thoi_gian_vao = models.DateTimeField(auto_now_add=True, verbose_name="Giờ Check-in")
    thoi_gian_ra = models.DateTimeField(null=True, blank=True, verbose_name="Giờ Check-out / In bill")
    
    # TÀI CHÍNH & SỐ LƯỢNG
    so_khach = models.IntegerField(default=1, verbose_name="Số lượng khách")
    tong_tien_hang = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Tổng tiền hàng")
    ma_voucher = models.CharField(max_length=50, blank=True, null=True)
    chiet_khau = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Giảm giá / Voucher")
    vat_phu_thu = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="VAT & Phụ thu khác")
    khach_can_tra = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Khách cần trả")
    
    # THANH TOÁN (Thay thế bảng ThanhToan)
    phuong_thuc_tt = models.CharField(max_length=20, choices=PAYMENT_METHODS, blank=True, null=True, verbose_name="Phương thức TT")
    so_tien_thu = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="Số tiền đã thu")
    ma_giao_dich_ngan_hang = models.CharField(max_length=100, blank=True, null=True, verbose_name="Mã giao dịch")
    ngay_thanh_toan = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian giao dịch")

    ghi_chu = models.TextField(blank=True, null=True, verbose_name="Ghi chú hóa đơn")
    trang_thai = models.CharField(max_length=20, choices=STATUS_CHOICES, default='dang_phuc_vu')

    def __str__(self):
        ten_ban = self.ban_an.ten_ban if self.ban_an else 'Mang đi'
        return f"{self.ma_hoa_don or 'NEW'} - {ten_ban}"

    def save(self, *args, **kwargs):
        if not self.ma_hoa_don:
            # ✅ FIX RACE CONDITION: Lưu trước để DB tự cấp id (guaranteed unique),
            # rồi dùng id thực đó để tạo ma_hoa_don — không bao giờ bị duplicate.
            super().save(*args, **kwargs)
            self.ma_hoa_don = f"INV-{self.id:05d}"
            super().save(update_fields=['ma_hoa_don'])
            return
        super().save(*args, **kwargs)



class ChiTietHoaDon(models.Model):
    hoa_don = models.ForeignKey(HoaDon, on_delete=models.CASCADE, related_name='chi_tiet', verbose_name="Thuộc Hóa Đơn")
    
    thuc_don = models.ForeignKey(ThucDon, on_delete=models.SET_NULL, null=True, blank=True)
    
    ten_mon_luu_tru = models.CharField(max_length=255, verbose_name="Tên món (Snapshot)")
    don_gia_luu_tru = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Đơn giá (Snapshot)")
    so_luong = models.IntegerField(default=1, verbose_name="Số lượng")
    so_luong_da_in = models.IntegerField(default=0, verbose_name="Số lượng đã in bếp")
    thanh_tien = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Thành tiền")
    
    thoi_gian_order = models.DateTimeField(auto_now_add=True)
    ghi_chu = models.CharField(max_length=255, blank=True, null=True, verbose_name="Ghi chú (Ít đá, không cay...)")

    def __str__(self):
        return f"{self.so_luong}x {self.ten_mon_luu_tru} ({self.hoa_don.ma_hoa_don})"

    def save(self, *args, **kwargs):
        if self.don_gia_luu_tru and self.so_luong:
            self.thanh_tien = self.don_gia_luu_tru * self.so_luong
        super().save(*args, **kwargs)