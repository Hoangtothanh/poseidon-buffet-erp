import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poseidon.settings')
django.setup()

from customers.models import Voucher

vouchers_data = [
    {"ma_code": "GIAM10", "muc_giam": "10%", "dieu_kien_toi_thieu": 500000, "ngay_het_han": date.today() + timedelta(days=30)},
    {"ma_code": "GIAM20", "muc_giam": "20%", "dieu_kien_toi_thieu": 1000000, "ngay_het_han": date.today() + timedelta(days=30)},
    {"ma_code": "TRU50K", "muc_giam": "50000", "dieu_kien_toi_thieu": 300000, "ngay_het_han": date.today() + timedelta(days=30)},
    {"ma_code": "TRU100K", "muc_giam": "100000", "dieu_kien_toi_thieu": 800000, "ngay_het_han": date.today() + timedelta(days=30)},
    {"ma_code": "POSEIDON500", "muc_giam": "500000", "dieu_kien_toi_thieu": 2000000, "ngay_het_han": date.today() + timedelta(days=30)},
]

print("Đang tạo danh sách Voucher mới...")

for v in vouchers_data:
    obj, created = Voucher.objects.get_or_create(
        ma_code=v["ma_code"],
        defaults={
            "muc_giam": v["muc_giam"],
            "dieu_kien_toi_thieu": v["dieu_kien_toi_thieu"],
            "ngay_het_han": v["ngay_het_han"],
            "trang_thai": True
        }
    )
    if not created:
        obj.muc_giam = v["muc_giam"]
        obj.dieu_kien_toi_thieu = v["dieu_kien_toi_thieu"]
        obj.ngay_het_han = v["ngay_het_han"]
        obj.trang_thai = True
        obj.save()
        print(f"Đã cập nhật voucher: {obj.ma_code}")
    else:
        print(f"Đã tạo voucher mới: {obj.ma_code}")

print("Hoàn tất thêm Voucher!")
