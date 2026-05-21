from django.db import models
from django.utils import timezone



# ==========================================
# 1. MODEL: NHẬT KÝ CHẠY AI (AI Engine Log)
# Dùng để hiển thị trạng thái "AI Engine: ONLINE" và độ chính xác của mô hình
# ==========================================
class AIEngineLog(models.Model):
    MODULE_CHOICES = [
        ('traffic', 'Dự đoán lượng khách'),
        ('inventory', 'Dự đoán tiêu thụ nguyên liệu'),
        ('menu', 'Tối ưu thực đơn (BCG Matrix)'),
    ]
    
    module_name = models.CharField(max_length=50, choices=MODULE_CHOICES, verbose_name="Phân hệ AI")
    lan_chay_cuoi = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian phân tích")
    do_chinh_xac = models.FloatField(help_text="Độ chính xác mô hình (%) - Confidence Score", verbose_name="Độ chính xác (%)")
    trang_thai = models.BooleanField(default=True, verbose_name="Trạng thái hoạt động")

    class Meta:
        verbose_name = "Nhật ký AI"
        verbose_name_plural = "1. Nhật ký hệ thống AI"

    def __str__(self):
        return f"AI {self.get_module_name_display()} - {self.do_chinh_xac}%"

# ==========================================
# 2. MODEL: DỰ ĐOÁN TIÊU THỤ NGUYÊN LIỆU / MÓN ĂN
# Phục vụ trang: ai_prediction.html
# ==========================================
class AIDuDoanTieuThu(models.Model):
    TREND_CHOICES = [
        ('tang', 'Tăng đột biến'),
        ('giam', 'Giảm mạnh'),
        ('binh_thuong', 'Bình thường'),
    ]

    ngay_du_doan = models.DateField(default=timezone.now, verbose_name="Ngày dự đoán")
    ten_mon = models.CharField(max_length=255, verbose_name="Tên món / Nguyên liệu")
    nhom_mon = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nhóm món (Thịt/Hải sản/Tráng miệng)")
    
    tieu_thu_ky_truoc = models.FloatField(verbose_name="Tiêu thụ kỳ trước (Kg/Phần)")
    ai_du_doan_tieu_thu = models.FloatField(verbose_name="AI Dự đoán kỳ này (Kg/Phần)")
    don_vi = models.CharField(max_length=20, default="Kg", verbose_name="Đơn vị tính")
    
    bien_dong_phan_tram = models.FloatField(verbose_name="Biến động (%)")
    xu_huong = models.CharField(max_length=20, choices=TREND_CHOICES, verbose_name="Xu hướng")
    
    loi_khuyen_ai = models.TextField(verbose_name="Hành động đề xuất (Prep List Action)")

    class Meta:
        verbose_name = "Dự đoán nguyên liệu"
        verbose_name_plural = "2. AI Dự đoán tiêu thụ"
        ordering = ['-ngay_du_doan', '-bien_dong_phan_tram']

    def __str__(self):
        return f"{self.ten_mon} - {self.ngay_du_doan}"

# ==========================================
# 3. MODEL: MA TRẬN TỐI ƯU THỰC ĐƠN (BCG MATRIX)
# Phục vụ trang: ai_menu_optimization.html
# ==========================================
class AIPhanTichThucDon(models.Model):
    MATRIX_CHOICES = [
        ('star', 'Ngôi Sao (Stars)'),
        ('horse', 'Ngựa Cày (Plowhorses)'),
        ('puzzle', 'Câu Đố (Puzzles)'),
        ('dog', 'Chó Mực (Dogs)'),
    ]

    thang_phan_tich = models.DateField(verbose_name="Tháng phân tích (Dữ liệu đầu tháng)")
    ten_mon = models.CharField(max_length=255, verbose_name="Tên món ăn")
    nhom_mon = models.CharField(max_length=100, verbose_name="Nhóm món")
    
    # Tọa độ biểu đồ Scatter
    ty_suat_loi_nhuan = models.FloatField(help_text="Trục Y (0-100)", verbose_name="Biên lợi nhuận (%)")
    do_pho_bien = models.FloatField(help_text="Trục X (0-100)", verbose_name="Độ phổ biến (Lượt lấy)")
    
    phan_loai_bcg = models.CharField(max_length=20, choices=MATRIX_CHOICES, verbose_name="Phân loại ma trận")
    
    food_cost = models.FloatField(verbose_name="Food Cost (%)")
    ty_le_hao_hut = models.FloatField(verbose_name="Tỷ lệ hao hụt/bỏ đi (%)")
    
    loi_khuyen_ai = models.TextField(verbose_name="Đề xuất hành động (Giữ/Bỏ/Tăng giá/Quảng bá)")

    class Meta:
        verbose_name = "Phân tích thực đơn"
        verbose_name_plural = "3. AI Tối ưu thực đơn (BCG)"
        ordering = ['-thang_phan_tich', 'phan_loai_bcg']

    def __str__(self):
        return f"[{self.get_phan_loai_bcg_display()}] {self.ten_mon}"

# ==========================================
# 4. MODEL: DỰ ĐOÁN LƯỢNG KHÁCH (FOOTFALL TRAFFIC)
# Phục vụ trang: ai_customer_traffic.html
# ==========================================
class AIDuDoanLuuLuong(models.Model):
    CA_LAM_VIEC = [
        ('sang', 'Ca Sáng (10h-15h)'),
        ('toi', 'Ca Tối (17h-22h)'),
        ('ca_ngay', 'Cả ngày'),
    ]
    
    STATUS_CHOICES = [
        ('vang', 'Vắng (<40%)'),
        ('binh_thuong', 'Bình thường (40-75%)'),
        ('dong', 'Đông (75-95%)'),
        ('qua_tai', 'Quá tải / Full (>95%)'),
    ]

    ngay_du_doan = models.DateField(verbose_name="Ngày")
    ca_lam_viec = models.CharField(max_length=20, choices=CA_LAM_VIEC, verbose_name="Ca làm việc")
    
    khach_thuc_te = models.IntegerField(null=True, blank=True, help_text="Bỏ trống nếu là ngày ở tương lai", verbose_name="Khách thực tế (Pax)")
    ai_du_doan_khach = models.IntegerField(verbose_name="AI Dự đoán (Pax)")
    
    ty_le_lap_day = models.FloatField(verbose_name="Tỷ lệ lấp đầy dự kiến (%)")
    trang_thai = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name="Trạng thái cảnh báo")
    
    doanh_thu_ky_vong = models.IntegerField(verbose_name="Doanh thu kỳ vọng (VNĐ)")
    
    loi_khuyen_van_hanh = models.TextField(verbose_name="Đề xuất vận hành (Nhân sự/Bàn ghế)")

    class Meta:
        verbose_name = "Dự đoán lượng khách"
        verbose_name_plural = "4. AI Phân tích lưu lượng"
        ordering = ['-ngay_du_doan']

    def __str__(self):
        return f"{self.ngay_du_doan} ({self.get_ca_lam_viec_display()}) - {self.ai_du_doan_khach} Pax"