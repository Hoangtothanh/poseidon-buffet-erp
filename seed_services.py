import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poseidon.settings')
django.setup()

from menu.models import ThucDon

services_data = [
    {"ten": "Phí mang rượu vang", "gia": 200000, "mo_ta": "Phí phụ thu khi khách mang rượu vang từ ngoài vào (tính theo chai)"},
    {"ten": "Phí mang rượu mạnh", "gia": 300000, "mo_ta": "Phí phụ thu khi khách mang rượu mạnh từ ngoài vào (tính theo chai)"},
    {"ten": "Phí mang bia", "gia": 10000, "mo_ta": "Phí phụ thu khi khách mang bia từ ngoài vào (tính theo lon/chai)"},
    {"ten": "Phí mang bánh kem", "gia": 50000, "mo_ta": "Phí phụ thu khi khách mang bánh kem từ ngoài vào"},
    {"ten": "Phụ thu phòng VIP", "gia": 500000, "mo_ta": "Phí phụ thu sử dụng phòng VIP"},
    {"ten": "Phí dọn dẹp đặc biệt", "gia": 100000, "mo_ta": "Phí phụ thu khi khách hàng làm bẩn nôn trớ cần dọn dẹp đặc biệt"},
]

print("Đang thêm dữ liệu phí dịch vụ phụ thu...")

for item in services_data:
    obj, created = ThucDon.objects.get_or_create(
        ten_mon=item["ten"],
        defaults={
            "loai_mon": "dich_vu",
            "danh_muc": "phu_thu",
            "gia_ban": item["gia"],
            "gia_von": 0,
            "mo_ta": item["mo_ta"],
            "trang_thai": True
        }
    )
    if created:
        print(f"Đã thêm: {obj.ten_mon}")
    else:
        obj.loai_mon = "dich_vu"
        obj.danh_muc = "phu_thu"
        obj.gia_ban = item["gia"]
        obj.mo_ta = item["mo_ta"]
        obj.save()
        print(f"Đã cập nhật: {obj.ten_mon}")

print("Hoàn tất!")
