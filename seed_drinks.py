import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poseidon.settings')
django.setup()

from menu.models import ThucDon

drinks_data = [
    {"ten": "Bia Tiger Platinum", "danh_muc": "bia_ruou", "gia": 35000, "img": "beverages/Bia_Tiger_Platinum.jpg"},
    {"ten": "Bia Tiger Sleek", "danh_muc": "bia_ruou", "gia": 35000, "img": "beverages/Bia_Tiger_Sleek.webp"},
    {"ten": "Rượu Chateau Les Pháp", "danh_muc": "bia_ruou", "gia": 550000, "img": "beverages/Chateau_Les_Pháp.png"},
    {"ten": "Rượu Luis Felipe Chile", "danh_muc": "bia_ruou", "gia": 650000, "img": "beverages/Luis_Felipe_Chile.jpg"},
    {"ten": "Rượu McGuigan Úc", "danh_muc": "bia_ruou", "gia": 450000, "img": "beverages/McGuigan_Úc.jpg"},
    {"ten": "Nước chanh leo", "danh_muc": "nuoc_ngot", "gia": 35000, "img": "beverages/Nước_chanh_leo.PNG"},
    {"ten": "Nước suối Aquafina", "danh_muc": "nuoc_ngot", "gia": 15000, "img": "beverages/Nước_suối_Aquafina.webp"},
    {"ten": "Nước ép", "danh_muc": "nuoc_ngot", "gia": 45000, "img": "beverages/Nước_ép.png"},
    {"ten": "Rượu Soju Hàn Quốc", "danh_muc": "bia_ruou", "gia": 65000, "img": "beverages/Rượu_Soju_Hàn_Quốc.png"},
    {"ten": "Nước cam Twister", "danh_muc": "nuoc_ngot", "gia": 20000, "img": "beverages/Twister.jpg"},
    {"ten": "Vang đỏ 1887 Chile", "danh_muc": "bia_ruou", "gia": 400000, "img": "beverages/Vang_đỏ_1887_Chile.png"},
    {"ten": "Vodka Putinka", "danh_muc": "bia_ruou", "gia": 300000, "img": "beverages/Vodka_Putinka.webp"},
    {"ten": "Pepsi", "danh_muc": "nuoc_ngot", "gia": 20000, "img": "beverages/pepsi.jpg"},
    {"ten": "Bạc xỉu", "danh_muc": "nuoc_ngot", "gia": 35000, "img": "menu/bacxiu.jpg"}
]

print("Đang thêm dữ liệu đồ uống...")

for item in drinks_data:
    obj, created = ThucDon.objects.get_or_create(
        ten_mon=item["ten"],
        defaults={
            "loai_mon": "do_uong",
            "danh_muc": item["danh_muc"],
            "gia_ban": item["gia"],
            "gia_von": item["gia"] * 0.6,
            "hinh_anh": item["img"],
            "trang_thai": True
        }
    )
    if created:
        print(f"Đã thêm: {obj.ten_mon}")
    else:
        obj.hinh_anh = item["img"]
        obj.danh_muc = item["danh_muc"]
        obj.gia_ban = item["gia"]
        obj.gia_von = item["gia"] * 0.6
        obj.save()
        print(f"Đã cập nhật: {obj.ten_mon}")

print("Hoàn tất!")
