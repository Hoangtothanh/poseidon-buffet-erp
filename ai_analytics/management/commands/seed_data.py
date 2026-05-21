from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
import random
from datetime import timedelta

# =====================================================================
# CHÚ Ý: BẠN HÃY KIỂM TRA VÀ SỬA LẠI TÊN APP Ở CÁC DÒNG IMPORT NÀY
# =====================================================================
from reception.models import KhuVuc, BanAn, KhachHang, PhieuDatBan
from menu.models import QuayLine, MonBuffet, GoiBuffet, DanhMuc, DoUongDichVu
# Dòng dưới này, thay chữ 'core' bằng tên app chứa bảng HoaDon của bạn (VD: pos, orders, banhang...)
from pos.models import HoaDon, ChiTietHoaDon, ThanhToan 

class Command(BaseCommand):
    help = 'Tự động tạo dữ liệu mẫu (Bàn ăn, Món ăn, Hóa đơn 7 ngày) cho nhà hàng Buffet'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Đang dọn dẹp dữ liệu cũ và gieo mầm dữ liệu mới...'))

        # 1. TẠO KHU VỰC & BÀN ĂN
        KhuVuc.objects.all().delete()
        t1 = KhuVuc.objects.create(ten_khu_vuc="Tầng 1 (Sảnh chính)")
        t2 = KhuVuc.objects.create(ten_khu_vuc="Tầng 2 (VIP)")

        for i in range(1, 11):
            BanAn.objects.create(khu_vuc=t1, ten_ban=f"Bàn T1-{i:02d}", so_ghe=4)
            BanAn.objects.create(khu_vuc=t2, ten_ban=f"Bàn T2-{i:02d}", so_ghe=6)
        
        self.stdout.write('✅ Đã tạo xong 20 Bàn ăn.')

        # 2. TẠO QUẦY LINE & MÓN BUFFET
        QuayLine.objects.all().delete()
        MonBuffet.objects.all().delete()
        
        q_hai_san = QuayLine.objects.create(ma_quay="Q01", ten_quay="Quầy Hải Sản Tươi", loai_icon="bi-water")
        q_nuong = QuayLine.objects.create(ma_quay="Q02", ten_quay="Quầy Đồ Nướng (BBQ)", loai_icon="bi-fire")
        q_trang_mieng = QuayLine.objects.create(ma_quay="Q03", ten_quay="Quầy Tráng Miệng", loai_icon="bi-cake2-fill")

        danh_sach_mon = [
            ("Hàu Nướng Mỡ Hành", q_hai_san, 35000), ("Sashimi Cá Hồi", q_hai_san, 380000),
            ("Ghẹ Hấp Sả", q_hai_san, 250000), ("Ba Chỉ Bò Mỹ", q_nuong, 160000),
            ("Dẻ Sườn Bò", q_nuong, 220000), ("Cánh Gà Sốt BBQ", q_nuong, 60000),
            ("Chè Khúc Bạch", q_trang_mieng, 85000), ("Hoa Quả Theo Mùa", q_trang_mieng, 25000)
        ]
        
        for ten, quay, gia_von in danh_sach_mon:
            MonBuffet.objects.create(ten_mon=ten, vi_tri_line=quay, gia_von_uoc_tinh=gia_von, trang_thai=True)

        self.stdout.write('✅ Đã tạo xong Quầy Line và Món Buffet.')

        # 3. TẠO GÓI BUFFET & ĐỒ UỐNG
        GoiBuffet.objects.all().delete()
        ve_nguoi_lon = GoiBuffet.objects.create(ten_goi="Vé Buffet Người Lớn", gia_ban=419000)
        ve_tre_em = GoiBuffet.objects.create(ten_goi="Vé Buffet Trẻ Em", gia_ban=199000)

        # 4. GIẢ LẬP HÓA ĐƠN TRONG 7 NGÀY QUA (Để AI và Biểu đồ có số liệu)
        HoaDon.objects.all().delete()
        ban_ans = list(BanAn.objects.all())
        user_admin, _ = User.objects.get_or_create(username='admin')

        today = timezone.now()
        
        self.stdout.write('Đang tạo hàng trăm hóa đơn giả lập (Vui lòng đợi 3 giây)...')
        
        for day_offset in range(7, -1, -1): # Chạy từ 7 ngày trước đến hôm nay
            ngay_gia_lap = today - timedelta(days=day_offset)
            
            # Mỗi ngày random từ 15 đến 35 bàn khách đến ăn
            so_ban_hom_nay = random.randint(15, 35) 
            
            for _ in range(so_ban_hom_nay):
                # Random giờ khách vào (Trưa: 11h-13h, Tối: 18h-20h)
                gio_vao = random.choice([11, 12, 13, 18, 19, 20])
                phut_vao = random.randint(0, 59)
                thoi_gian_vao_gia_lap = ngay_gia_lap.replace(hour=gio_vao, minute=phut_vao)
                
                so_nguoi_lon = random.randint(2, 6)
                tong_tien = so_nguoi_lon * ve_nguoi_lon.gia_ban
                
                # Nếu là ngày hôm nay và đang là giờ hiện tại, cho 1 vài bàn trạng thái "Đang ăn"
                trang_thai_hd = 'da_thanh_toan'
                if day_offset == 0 and gio_vao == today.hour and random.choice([True, False]):
                    trang_thai_hd = 'dang_phuc_vu'

                # BƯỚC LƯU HÓA ĐƠN
                hd = HoaDon.objects.create(
                    ban_an=random.choice(ban_ans),
                    nhan_vien=user_admin,
                    so_khach=so_nguoi_lon,
                    tong_tien_hang=tong_tien,
                    khach_can_tra=tong_tien,
                    trang_thai=trang_thai_hd
                )
                
                # Mẹo Django: Cập nhật lại thời gian vào vì trường auto_now_add không cho gán trực tiếp lúc create
                HoaDon.objects.filter(id=hd.id).update(thoi_gian_vao=thoi_gian_vao_gia_lap)
                
                # Chuyển trạng thái bàn nếu đang ăn
                if trang_thai_hd == 'dang_phuc_vu':
                    BanAn.objects.filter(id=hd.ban_an.id).update(trang_thai='dang_an')

        self.stdout.write(self.style.SUCCESS('\n🎉 XUẤT SẮC! Toàn bộ dữ liệu nhà hàng đã được gieo mầm thành công!'))
        self.stdout.write(self.style.SUCCESS('👉 Bước tiếp theo: Chạy lệnh "python manage.py run_ai_bcg" để AI bắt đầu học.'))