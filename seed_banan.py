import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poseidon.settings')
django.setup()

from reception.models import BanAn, KhuVuc

print("Xóa toàn bộ khu vực và bàn cũ...")
BanAn.objects.all().delete()
KhuVuc.objects.all().delete()

khu_vuc_names = ['Khu Vực A', 'Khu Vực B', 'Khu Vực C']

print("Đang tạo sơ đồ bàn mới...")
for ten_khu in khu_vuc_names:
    khu = KhuVuc.objects.create(ten_khu_vuc=ten_khu, mo_ta=f"Khu vực ngoài sảnh {ten_khu}")
    prefix = ten_khu.split()[-1] # Lấy chữ cái A, B, C
    for i in range(1, 11):
        ten_ban = f"Bàn {prefix}{i}"
        BanAn.objects.create(
            ten_ban=ten_ban,
            khu_vuc=khu,
            so_ghe=random.choice([2, 4, 6, 8, 10]),
            trang_thai='trong'
        )

print(f"Hoàn tất! Đã tạo {KhuVuc.objects.count()} khu vực và {BanAn.objects.count()} bàn ăn.")
