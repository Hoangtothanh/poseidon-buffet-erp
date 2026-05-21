from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone

class SystemSetting(models.Model):
    # --- THÔNG TIN ĐỊNH DANH ---
    restaurant_name = models.CharField(max_length=255, default="Poseidon Buffet Premium")
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)    
    hotline = models.CharField(max_length=20, default="1900 8888")
    address = models.CharField(max_length=500, default="Tầng 4, Vincom Center, Hà Nội")
    
    # --- QUY ĐỊNH VẬN HÀNH ---
    open_time = models.TimeField(default="10:00")
    close_time = models.TimeField(default="22:30")
    hold_table_time = models.IntegerField(default=15, verbose_name="Thời gian giữ bàn (Phút)")
    vat_tax = models.IntegerField(default=8)
    service_charge = models.IntegerField(default=5)
    deposit_percent = models.IntegerField(default=20, verbose_name="Tỷ lệ cọc (%)")
    
    # --- TÍCH HỢP THANH TOÁN ---
    bank_id = models.CharField(max_length=50, default='MB', verbose_name='Mã Ngân hàng')
    bank_account_no = models.CharField(max_length=50, blank=True, null=True, verbose_name='Số Tài khoản')
    bank_account_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Tên Chủ Tài Khoản')
    
    # --- CẤU HÌNH AI ---
    ai_dataset_window = models.CharField(max_length=50, default="3_months")
    ai_prediction_window = models.CharField(max_length=50, default="7_days")
    ai_weather_sync = models.BooleanField(default=True)

    def __str__(self):
        return "Cấu hình Hệ thống Poseidon"


class SystemLog(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Thông tin (Xanh/Đen)'),
        ('warning', 'Cảnh báo (Vàng)'),
        ('danger', 'Nguy hiểm (Đỏ)'),
    ]
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    module = models.CharField(max_length=100)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='info')

    def __str__(self):
        return f"[{self.timestamp.strftime('%d/%m/%Y %H:%M')}] {self.user.username if self.user else 'System'}: {self.action}"


# ==========================================
# MA TRẬN PHÂN QUYỀN MỚI (CHUẨN CRUD CHUYÊN SÂU)
# ==========================================
class QuyenTruyCap(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='quyen')
    description = models.CharField(max_length=255, blank=True, null=True) 
    
    # 1. Module Sơ đồ Bàn (Table)
    table_view = models.BooleanField(default=False)
    table_edit = models.BooleanField(default=False)

    # 2. Module Đặt bàn & Khách hàng (Booking)
    booking_view = models.BooleanField(default=False)
    booking_edit = models.BooleanField(default=False)
    booking_delete = models.BooleanField(default=False)

    # 3. Module Bán hàng (POS)
    pos_view = models.BooleanField(default=False)
    pos_edit = models.BooleanField(default=False, verbose_name="Quyền lên Order")
    pos_checkout = models.BooleanField(default=False, verbose_name="Quyền Thanh toán")

    # 4. Module Thực đơn (Menu)
    menu_view = models.BooleanField(default=False)
    menu_edit = models.BooleanField(default=False)
    menu_delete = models.BooleanField(default=False)

    # 5. Module Kho Nguyên liệu (Inventory)
    inventory_view = models.BooleanField(default=False)
    inventory_edit = models.BooleanField(default=False)
    inventory_delete = models.BooleanField(default=False)

    # 6. Module Báo cáo Thống kê
    report_view = models.BooleanField(default=False)

    # 7. Admin Hệ thống
    system_all = models.BooleanField(default=False)

    def __str__(self):
        return f"Quyền hạn của {self.group.name}"