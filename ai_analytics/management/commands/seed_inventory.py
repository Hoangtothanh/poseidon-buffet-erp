from django.core.management.base import BaseCommand
import random

# KIỂM TRA TÊN APP: Sửa chữ 'inventory' dưới đây thành tên App chứa model Kho của bạn
from inventory.models import DanhMucNguyenLieu, NhaCungCap, NguyenLieu 

class Command(BaseCommand):
    help = 'Tự động tạo dữ liệu mẫu cho Kho Nguyên Vật Liệu (Hải sản, Thịt bò, Gia vị...)'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Đang nạp dữ liệu Kho Nguyên Vật Liệu (Inventory)...'))

        # 1. XÓA DỮ LIỆU CŨ CHO SẠCH SẼ
        NguyenLieu.objects.all().delete()
        NhaCungCap.objects.all().delete()
        DanhMucNguyenLieu.objects.all().delete()

        # 2. TẠO DANH MỤC NGUYÊN LIỆU
        dm_haisan = DanhMucNguyenLieu.objects.create(ten_danh_muc="Hải Sản Tươi Sống", ghi_chu="Nhập mới mỗi ngày")
        dm_thit = DanhMucNguyenLieu.objects.create(ten_danh_muc="Thịt (Bò, Gà, Heo)", ghi_chu="Đồ đông lạnh")
        dm_raucu = DanhMucNguyenLieu.objects.create(ten_danh_muc="Rau Củ Quả", ghi_chu="Dùng làm nộm, lẩu, salad")
        dm_giavi = DanhMucNguyenLieu.objects.create(ten_danh_muc="Gia Vị & Đồ Khô", ghi_chu="Dùng cho bếp nóng")
        dm_douong = DanhMucNguyenLieu.objects.create(ten_danh_muc="Đồ Uống (Chai/Lon)", ghi_chu="Phục vụ quầy Bar")

        # 3. TẠO NHÀ CUNG CẤP MẪU
        ncc_cp = NhaCungCap.objects.create(
            ten_ncc="Công ty Cổ phần CP Việt Nam", nguoi_lien_he="Anh Tuấn CP",
            so_dien_thoai="0901234567", dia_chi="KCN Biên Hòa 2",
            trang_thai=True, cong_no=15000000
        )
        ncc_hsd = NhaCungCap.objects.create(
            ten_ncc="Vựa Hải Sản Đại Dương", nguoi_lien_he="Chị Liên Cảng",
            so_dien_thoai="0987654321", dia_chi="Cảng cá Đồ Sơn",
            trang_thai=True, cong_no=8500000
        )

        # 4. DANH SÁCH 30 NGUYÊN LIỆU BUFFET
        # Format: (Tên, Danh mục, Đơn vị, Giá vốn TB, Tồn kho thực tế)
        nl_data = [
            # Hải Sản
            ("Hàu Sữa Cửa Lò", dm_haisan, "Kg", 32000, random.uniform(15, 50)),
            ("Sashimi Cá Hồi Na Uy", dm_haisan, "Kg", 380000, random.uniform(5, 15)),
            ("Ghẹ Xanh Cỡ Vừa", dm_haisan, "Kg", 250000, random.uniform(10, 30)),
            ("Bề Bề Tươi", dm_haisan, "Kg", 180000, random.uniform(8, 25)),
            ("Tôm Sú", dm_haisan, "Kg", 220000, random.uniform(15, 40)),
            ("Mực Ống Tươi", dm_haisan, "Kg", 150000, random.uniform(12, 35)),
            ("Ngao Hoa", dm_haisan, "Kg", 25000, random.uniform(30, 80)),
            ("Bạch Tuộc Tươi", dm_haisan, "Kg", 160000, random.uniform(10, 20)),
            
            # Thịt
            ("Ba Chỉ Bò Mỹ (Cuộn)", dm_thit, "Kg", 155000, random.uniform(30, 100)),
            ("Dẻ Sườn Bò Rút Xương", dm_thit, "Kg", 210000, random.uniform(15, 40)),
            ("Thịt Gà Ta (Đùi/Cánh)", dm_thit, "Kg", 55000, random.uniform(20, 60)),
            ("Ba Chỉ Heo Rút Sườn", dm_thit, "Kg", 85000, random.uniform(20, 50)),
            ("Nầm Bò Mỹ", dm_thit, "Kg", 175000, random.uniform(10, 30)),
            
            # Rau Củ
            ("Rau Xà Lách", dm_raucu, "Kg", 15000, random.uniform(5, 15)),
            ("Cải Thảo", dm_raucu, "Kg", 12000, random.uniform(10, 25)),
            ("Nấm Kim Châm", dm_raucu, "Kg", 25000, random.uniform(15, 30)),
            ("Ngô Ngọt", dm_raucu, "Kg", 18000, random.uniform(5, 20)),
            ("Khoai Tây (Cắt Sẵn)", dm_raucu, "Kg", 22000, random.uniform(20, 50)),
            ("Cà Chua Trái", dm_raucu, "Kg", 15000, random.uniform(5, 15)),
            ("Chanh Tươi", dm_raucu, "Kg", 20000, random.uniform(3, 8)),
            
            # Gia Vị & Khô
            ("Dầu Ăn Cái Lân", dm_giavi, "Lít", 45000, random.uniform(10, 50)),
            ("Nước Mắm Nam Ngư", dm_giavi, "Lít", 35000, random.uniform(10, 40)),
            ("Đường Cát Trắng", dm_giavi, "Kg", 22000, random.uniform(15, 60)),
            ("Bột Ngọt", dm_giavi, "Kg", 40000, random.uniform(10, 30)),
            ("Gạo ST25", dm_giavi, "Kg", 28000, random.uniform(30, 100)),
            ("Tương Ớt Chinsu", dm_giavi, "Can", 75000, random.uniform(5, 15)),
            
            # Đồ Uống Kho
            ("Bia Tiger Bạc (Lon)", dm_douong, "Lon", 14500, random.randint(120, 500)),
            ("Pepsi (Lon)", dm_douong, "Lon", 8500, random.randint(100, 300)),
            ("Nước Suối Aquafina", dm_douong, "Chai", 5000, random.randint(50, 200)),
            ("Rượu Soju Core", dm_douong, "Chai", 45000, random.randint(20, 100)),
        ]

        # 5. LƯU VÀO DATABASE
        for ten, danhmuc, donvi, gia, tonkho in nl_data:
            # Tạo 1 món nguyên liệu có tồn kho bị cạn (Mô phỏng chức năng cảnh báo đỏ)
            ton_kho_thuc = tonkho
            if ten == "Ba Chỉ Bò Mỹ (Cuộn)":
                ton_kho_thuc = 3.5 # Ép Bò Mỹ cạn kho để test cảnh báo

            NguyenLieu.objects.create(
                ten_nguyen_lieu=ten,
                danh_muc=danhmuc,
                don_vi_tinh=donvi,
                don_gia_trung_binh=gia,
                ton_kho=round(ton_kho_thuc, 1),
                muc_canh_bao=10.0 # Báo động đỏ nếu dưới 10kg
            )
            self.stdout.write(f" - Đã nạp NL: {ten}")

        self.stdout.write(self.style.SUCCESS('\n🎉 Đã nạp thành công 30 mặt hàng vào Kho Nguyên Vật Liệu!'))