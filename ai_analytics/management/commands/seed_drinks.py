from django.core.management.base import BaseCommand
from menu.models import DanhMuc, DoUongDichVu # Sửa chữ 'menu' thành tên app của bạn nếu cần

class Command(BaseCommand):
    help = 'Tự động tạo danh mục và menu Đồ uống & Phụ thu'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Đang nạp dữ liệu Menu Đồ Uống & Phụ Thu...'))

        # 1. XÓA DỮ LIỆU CŨ ĐỂ TRÁNH TRÙNG LẶP
        DanhMuc.objects.all().delete()
        DoUongDichVu.objects.all().delete()

        # 2. TẠO CÁC DANH MỤC
        dm_softdrink = DanhMuc.objects.create(ten_danh_muc="Soft Drinks & Nước Hoa Quả", icon="bi-cup-straw")
        dm_beer = DanhMuc.objects.create(ten_danh_muc="Beer & Liquor", icon="bi-cup-hot")
        dm_wine = DanhMuc.objects.create(ten_danh_muc="Wine (Vang Nhập Khẩu)", icon="bi-droplet")
        dm_phuthu = DanhMuc.objects.create(ten_danh_muc="Phí Dịch Vụ Mang Đồ Uống", icon="bi-receipt") # Có chữ "Phí" sẽ tự nhảy SKU thành FEE-

        # 3. DANH SÁCH MÓN VÀ GIÁ BÁN (Giá vốn tạm tính bằng ~50% giá bán)
        menu_data = [
            # Soft Drinks
            {"ten": "Nước suối Aquafina", "gia_ban": 27000, "dm": dm_softdrink},
            {"ten": "Twister / Rockstar / Sting", "gia_ban": 35000, "dm": dm_softdrink},
            {"ten": "Pepsi / 7UP (Thường & Chanh)", "gia_ban": 35000, "dm": dm_softdrink},
            {"ten": "Nước ép (Dứa, Dưa hấu, Cam, Cà rốt, Ổi...)", "gia_ban": 45000, "dm": dm_softdrink},
            {"ten": "Nước chanh leo / Chanh tươi", "gia_ban": 45000, "dm": dm_softdrink},
            
            # Beer & Liquor
            {"ten": "Bia Tiger Sleek / Crystal / Heineken", "gia_ban": 40000, "dm": dm_beer},
            {"ten": "Bia Tiger Platinum", "gia_ban": 40000, "dm": dm_beer},
            {"ten": "Poseidon Premium", "gia_ban": 45000, "dm": dm_beer},
            {"ten": "Rượu Soju Hàn Quốc", "gia_ban": 130000, "dm": dm_beer},
            {"ten": "Vodka Putinka / Kozak / Cá ngựa", "gia_ban": 300000, "dm": dm_beer},
            
            # Wine
            {"ten": "Vang đỏ/trắng 1887 Chile", "gia_ban": 380000, "dm": dm_wine},
            {"ten": "Vang đỏ/trắng Luis Felipe Chile", "gia_ban": 530000, "dm": dm_wine},
            {"ten": "Vang đỏ/trắng McGuigan Úc", "gia_ban": 560000, "dm": dm_wine},
            {"ten": "Vang đỏ/trắng Chateau Les Pháp", "gia_ban": 630000, "dm": dm_wine},
            
            # Phí Dịch Vụ
            {"ten": "Phụ thu Nước ngọt / Nước suối", "gia_ban": 20000, "dm": dm_phuthu},
            {"ten": "Phụ thu Bia lon", "gia_ban": 25000, "dm": dm_phuthu},
            {"ten": "Phụ thu Rượu quê (lít)", "gia_ban": 150000, "dm": dm_phuthu},
            {"ten": "Phụ thu Rượu vang / Vodka (chai)", "gia_ban": 200000, "dm": dm_phuthu},
            {"ten": "Phụ thu Rượu Whisky (chai)", "gia_ban": 500000, "dm": dm_phuthu},
        ]

        # 4. CHẠY VÒNG LẶP ĐỂ ĐƯA VÀO DATABASE
        for item in menu_data:
            gia_von_tinh_nham = int(item["gia_ban"] * 0.45) # Giả lập giá vốn chiếm 45% giá bán
            DoUongDichVu.objects.create(
                ten_mon=item["ten"],
                danh_muc=item["dm"],
                gia_ban=item["gia_ban"],
                gia_von=gia_von_tinh_nham,
                con_hang=True,
                hien_thi_pos=True
            )
            self.stdout.write(f" - Đã thêm: {item['ten']} ({item['gia_ban']}đ)")

        self.stdout.write(self.style.SUCCESS('\n🎉 Đã nạp thành công toàn bộ Menu Đồ uống và Phụ thu vào Database!'))