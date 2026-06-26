"""
reset_invoices.py
=================
Xóa TOÀN BỘ hóa đơn đã thanh toán (da_thanh_toan) và bơm lại
với CHỈ 2 phương thức POS:
  - Tiền mặt     (70%)
  - Chuyển khoản (30%)

Dữ liệu: 30 ngày qua, mỗi ngày 50–120 hóa đơn (cuối tuần nhiều hơn)

Sử dụng:
  python reset_invoices.py
"""

import os
import sys
import django
import random
from datetime import date, timedelta
from django.utils import timezone
import datetime as dt

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poseidon.settings')
django.setup()

from django.contrib.auth.models import User
from pos.models import HoaDon, ChiTietHoaDon
from menu.models import ThucDon
from reception.models import BanAn
from customers.models import KhachHang

# ============================================================
# BƯỚC 1: XÓA SẠCH HÓA ĐƠN CŨ
# ============================================================
print("=" * 60)
print("🗑️  RESET: Xóa toàn bộ hóa đơn đã thanh toán...")
print("=" * 60)

da_tt = HoaDon.objects.filter(trang_thai='da_thanh_toan')
count_before = da_tt.count()
da_tt.delete()
print(f"  ✅ Đã xóa {count_before} hóa đơn 'da_thanh_toan'.")

# Xóa cả hóa đơn đã hủy (không cần thiết giữ lại)
da_huy = HoaDon.objects.filter(trang_thai='da_huy')
count_huy = da_huy.count()
da_huy.delete()
print(f"  ✅ Đã xóa thêm {count_huy} hóa đơn 'da_huy'.")
print()

# ============================================================
# BƯỚC 2: KIỂM TRA DỮ LIỆU CHUẨN BỊ
# ============================================================
ban_list    = list(BanAn.objects.exclude(trang_thai='da_xoa'))
buffet_list = list(ThucDon.objects.filter(loai_mon='goi_buffet', trang_thai=True))
drink_list  = list(ThucDon.objects.filter(loai_mon='do_uong', trang_thai=True))
kh_list     = list(KhachHang.objects.filter(is_active=True))
nv_list     = list(User.objects.filter(nhanvien__isnull=False))

print(f"📋 Chuẩn bị:")
print(f"   • Bàn ăn     : {len(ban_list)}")
print(f"   • Gói buffet : {len(buffet_list)}")
print(f"   • Đồ uống    : {len(drink_list)}")
print(f"   • Khách hàng : {len(kh_list)}")
print(f"   • Nhân viên  : {len(nv_list)}")

if not ban_list or not buffet_list:
    print("\n❌ Thiếu bàn ăn hoặc gói buffet. Thoát.")
    sys.exit(1)

# ============================================================
# BƯỚC 3: SEED HÓA ĐƠN MỚI — CHỈ 2 PHƯƠNG THỨC POS
# ============================================================
print()
print("=" * 60)
print("🚀 SEED: Bơm hóa đơn mới (30 ngày, 2 PT thanh toán)...")
print("=" * 60)

# Chỉ 2 phương thức khớp với máy POS thực tế
PAYMENT_METHODS = ['tien_mat', 'chuyen_khoan']
PAYMENT_WEIGHTS = [0.70,       0.30]           # 70% tiền mặt / 30% QR

HOUR_CHOICES  = [11, 12, 13, 17, 18, 19, 20, 21]
HOUR_WEIGHTS  = [0.08, 0.22, 0.10, 0.05, 0.15, 0.22, 0.13, 0.05]

GROUP_CHOICES = [2, 4, 6, 8, 10]
GROUP_WEIGHTS = [0.30, 0.35, 0.20, 0.10, 0.05]

rng = random.Random(2025)
today = timezone.now().date()
created_count = 0

# Tắt auto_now_add để set thời gian lịch sử
HoaDon._meta.get_field('thoi_gian_vao').auto_now_add = False
ChiTietHoaDon._meta.get_field('thoi_gian_order').auto_now_add = False

try:
    for i in range(30, 0, -1):
        d_date = today - timedelta(days=i)
        is_weekend = d_date.weekday() >= 4  # Thứ 6, 7, CN
        num_bills = rng.randint(80, 120) if is_weekend else rng.randint(50, 75)

        day_invoices = []
        for _ in range(num_bills):
            hour   = rng.choices(HOUR_CHOICES, weights=HOUR_WEIGHTS, k=1)[0]
            minute = rng.randint(0, 59)
            so_khach = rng.choices(GROUP_CHOICES, weights=GROUP_WEIGHTS, k=1)[0]

            checkin_dt  = timezone.make_aware(
                dt.datetime(d_date.year, d_date.month, d_date.day,
                            hour, minute, rng.randint(0, 59))
            )
            duration_min = rng.randint(90, 150)
            checkout_dt  = checkin_dt + timedelta(minutes=duration_min)

            buffet     = rng.choice(buffet_list)
            phuong_thuc = rng.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS, k=1)[0]
            nhan_vien  = rng.choice(nv_list) if nv_list else None
            khach_hang = rng.choice(kh_list) if (kh_list and rng.random() < 0.35) else None

            # Tiền buffet
            tien_buffet = int(buffet.gia_ban) * so_khach
            tong_tien   = tien_buffet

            # Đồ uống (35% khả năng)
            drink_details = []
            if drink_list and rng.random() < 0.35:
                drink    = rng.choice(drink_list)
                sl_drink = rng.randint(1, max(1, so_khach // 2))
                tien_drink = int(drink.gia_ban) * sl_drink
                tong_tien  += tien_drink
                drink_details.append((drink, sl_drink, tien_drink))

            # Tạo hóa đơn
            hd = HoaDon(
                ban_an          = rng.choice(ban_list),
                khach_hang      = khach_hang,
                nhan_vien       = nhan_vien,
                thoi_gian_vao   = checkin_dt,
                thoi_gian_ra    = checkout_dt,      # ← Bắt buộc
                so_khach        = so_khach,
                tong_tien_hang  = tong_tien,
                chiet_khau      = 0,
                vat_phu_thu     = 0,
                khach_can_tra   = tong_tien,
                phuong_thuc_tt  = phuong_thuc,      # ← tien_mat | chuyen_khoan
                so_tien_thu     = tong_tien,
                ngay_thanh_toan = checkout_dt,       # ← Dùng cho Transaction Log
                trang_thai      = 'da_thanh_toan',
                ghi_chu         = 'SEED_HISTORY',
            )
            hd.save()

            # Chi tiết: Vé buffet
            ChiTietHoaDon.objects.create(
                hoa_don         = hd,
                thuc_don        = buffet,
                ten_mon_luu_tru = buffet.ten_mon,
                don_gia_luu_tru = buffet.gia_ban,
                so_luong        = so_khach,
                thanh_tien      = tien_buffet,
                thoi_gian_order = checkin_dt,
            )

            # Chi tiết: Đồ uống
            for drink, sl_d, t_d in drink_details:
                ChiTietHoaDon.objects.create(
                    hoa_don         = hd,
                    thuc_don        = drink,
                    ten_mon_luu_tru = drink.ten_mon,
                    don_gia_luu_tru = drink.gia_ban,
                    so_luong        = sl_d,
                    thanh_tien      = t_d,
                    thoi_gian_order = checkin_dt + timedelta(minutes=rng.randint(5, 20)),
                )

            day_invoices.append(hd)
            created_count += 1

        print(f"  📅 {d_date.strftime('%d/%m/%Y')} ({'Cuối tuần' if is_weekend else 'Ngày thường':12s}) "
              f"→ {len(day_invoices):3d} HĐ  "
              f"[TM: {sum(1 for h in day_invoices if h.phuong_thuc_tt=='tien_mat'):3d} | "
              f"QR: {sum(1 for h in day_invoices if h.phuong_thuc_tt=='chuyen_khoan'):3d}]")

finally:
    HoaDon._meta.get_field('thoi_gian_vao').auto_now_add = True
    ChiTietHoaDon._meta.get_field('thoi_gian_order').auto_now_add = True

# ============================================================
# TỔNG KẾT
# ============================================================
total_tm = HoaDon.objects.filter(trang_thai='da_thanh_toan', phuong_thuc_tt='tien_mat').count()
total_qr = HoaDon.objects.filter(trang_thai='da_thanh_toan', phuong_thuc_tt='chuyen_khoan').count()
total_all = HoaDon.objects.filter(trang_thai='da_thanh_toan').count()

print()
print("=" * 60)
print(f"🎉 HOÀN TẤT! Đã tạo {created_count} hóa đơn.")
print(f"   • Tiền mặt     : {total_tm:,} HĐ ({total_tm/total_all*100:.1f}%)")
print(f"   • Chuyển khoản : {total_qr:,} HĐ ({total_qr/total_all*100:.1f}%)")
print(f"   • Tổng DB      : {total_all:,} HĐ")
print()
print("   → Kiểm tra tại: http://127.0.0.1:8000/invoices/")
print("=" * 60)
