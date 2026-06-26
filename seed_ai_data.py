"""
seed_ai_data.py
================
Script khởi tạo dữ liệu mẫu thông minh cho hệ thống AI Analytics Poseidon.

CHIẾN LƯỢC INCREMENTAL (Bổ sung thiếu, không xóa thừa):
  - Với mỗi ngày trong 30 ngày qua, kiểm tra số hóa đơn hiện có.
  - Nếu ngày đó ĐÃ ĐỦ số hóa đơn mục tiêu → BỎ QUA (không tạo thêm, không xóa).
  - Nếu ngày đó còn THIẾU → chỉ tạo phần còn thiếu.
  - Kết quả: chạy lần đầu ~5-10 giây, chạy lại gần như TỨC THÌ.

THAM SỐ DÒNG LỆNH:
  python seed_ai_data.py            → Incremental (mặc định, nhanh)
  python seed_ai_data.py --reset    → Xóa sạch và tạo lại toàn bộ (chậm, dùng khi cần reset)
  python seed_ai_data.py --status   → Chỉ xem trạng thái từng ngày, không tạo gì
"""

import os
import sys
import django
import random
from datetime import timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poseidon.settings')
django.setup()

from django.db.models import Count
from pos.models import HoaDon, ChiTietHoaDon
from menu.models import ThucDon
from reception.models import BanAn
from inventory.models import NguyenLieu, PhieuKho, ChiTietPhieuKho
from hrm.models import CaLamViec, NhanVien


# ==========================================
# CẤU HÌNH MỤC TIÊU
# ==========================================
TARGET_WEEKDAY_BILLS  = (60, 80)   # Ngày thường: 60–80 hóa đơn/ngày
TARGET_WEEKEND_BILLS  = (100, 125) # Cuối tuần:  100–125 hóa đơn/ngày
DAYS_WINDOW           = 30         # Số ngày sinh dữ liệu
AI_DATA_TAG           = "AI_TEST_DATA"

# Phân phối giờ cao điểm (trưa 11-13h, tối 18-21h, thấp điểm 14-17h)
HOUR_CHOICES  = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
HOUR_WEIGHTS  = [0.1, 0.3, 0.1, 0.02, 0.02, 0.02, 0.05, 0.1, 0.3, 0.2, 0.05]
GROUP_CHOICES = [2, 4, 6, 10]
GROUP_WEIGHTS = [0.4, 0.3, 0.2, 0.1]


def get_day_target(date_obj):
    """
    Tính số hóa đơn mục tiêu cho một ngày cụ thể.
    Dùng date.toordinal() làm seed để mỗi ngày luôn có cùng target khi gọi lại.
    → Đảm bảo tính nhất quán: chạy lần 1 hay lần 10, ngày X vẫn cùng target.
    """
    rng = random.Random(date_obj.toordinal())  # Seeded RNG riêng cho từng ngày
    is_weekend = date_obj.weekday() >= 4       # Thứ 6=4, Thứ 7=5, CN=6
    if is_weekend:
        return rng.randint(*TARGET_WEEKEND_BILLS)
    return rng.randint(*TARGET_WEEKDAY_BILLS)


def get_drink_call_prob(days_ago):
    """
    Xác suất gọi tháp bia: 3 ngày gần nhất thấp (10%) để kích AI cảnh báo Upsell.
    Các ngày trước đó bình thường (40%).
    """
    return 0.1 if days_ago <= 3 else 0.4


def setup_staff(today, nv_list):
    """Xếp ca làm việc hôm nay (reset mỗi lần chạy để demo AI cảnh báo workload)."""
    CaLamViec.objects.filter(ngay_lam_viec=today).delete()
    ca_trua = CaLamViec.objects.create(ngay_lam_viec=today, loai_ca='morning', bo_phan='service')
    ca_trua.nhan_vien.set(nv_list[:5])  # 5 NV ca trưa → đủ

    ca_toi = CaLamViec.objects.create(ngay_lam_viec=today, loai_ca='evening', bo_phan='service')
    ca_toi.nhan_vien.set(nv_list[5:7])  # 2 NV ca tối → cố tình thiếu → AI cảnh báo
    print("   ✅ Xếp ca: 5 NV ca trưa | 2 NV ca tối (kích hoạt AI Workload Warning)")


def setup_inventory(today):
    """Tạo nguyên liệu + phiếu xuất kho 7 ngày để AI JIT tính Burn Rate."""
    nl_bo,  _ = NguyenLieu.objects.get_or_create(
        ten_nguyen_lieu="Thịt Bò Mỹ",
        defaults={"don_vi_tinh": "Kg", "ton_kho": 10.0}   # Tồn thấp → AI cảnh báo
    )
    nl_cua, _ = NguyenLieu.objects.get_or_create(
        ten_nguyen_lieu="Cua Cà Mau",
        defaults={"don_vi_tinh": "Kg", "ton_kho": 5.0}    # Tồn thấp → AI cảnh báo
    )
    nl_rau, _ = NguyenLieu.objects.get_or_create(
        ten_nguyen_lieu="Rau Salad",
        defaults={"don_vi_tinh": "Kg", "ton_kho": 200.0}  # Tồn an toàn
    )

    # Reset phiếu xuất rồi tạo lại 7 ngày (nhỏ, nhanh)
    PhieuKho.objects.filter(loai_phieu='xuat').delete()
    for i in range(1, 8):
        d = today - timedelta(days=i)
        phieu = PhieuKho.objects.create(loai_phieu='xuat', ngay_thuc_hien=d)
        ChiTietPhieuKho.objects.create(phieu=phieu, nguyen_lieu=nl_bo,  so_luong=50)
        ChiTietPhieuKho.objects.create(phieu=phieu, nguyen_lieu=nl_cua, so_luong=30)
        ChiTietPhieuKho.objects.create(phieu=phieu, nguyen_lieu=nl_rau, so_luong=20)

    print("   ✅ Tồn kho: Bò 10kg | Cua 5kg | Rau 200kg + xuất kho 7 ngày (JIT Burn Rate)")


def build_bills_for_day(d_dt, days_ago, num_bills, ban_an_list,
                        ve_buffet, nuoc_ngot, thap_bia, extra_items, start_id):
    """
    Sinh `num_bills` HoaDon + ChiTietHoaDon cho ngày `d_dt`.
    Dùng RNG seeded theo (ordinal + start_id) để kết quả có thể tái tạo.
    Trả về (bills_list, details_list, last_id).
    """
    rng = random.Random(d_dt.date().toordinal() * 10000 + start_id)
    bills_to_create   = []
    details_to_create = []
    drink_prob = get_drink_call_prob(days_ago)
    counter = start_id

    for _ in range(num_bills):
        counter += 1
        hour_choice  = rng.choices(HOUR_CHOICES, weights=HOUR_WEIGHTS, k=1)[0]
        so_khach     = rng.choices(GROUP_CHOICES, weights=GROUP_WEIGHTS, k=1)[0]
        checkin_time = d_dt.replace(
            hour=hour_choice,
            minute=rng.randint(0, 59),
            second=rng.randint(0, 59),
            microsecond=0
        )

        # Tính tổng tiền từ các chi tiết
        tong_tien_hd = 0

        hd = HoaDon(
            ma_hoa_don=f"INV-AI-{counter}",
            ban_an=rng.choice(ban_an_list),
            thoi_gian_vao=checkin_time,
            so_khach=so_khach,
            khach_can_tra=0, # Sẽ cập nhật sau
            trang_thai='da_thanh_toan',
            ghi_chu=AI_DATA_TAG
        )
        hd.id = counter
        bills_to_create.append(hd)

        # Chi tiết: Vé buffet (luôn có)
        tien_ve = so_khach * ve_buffet.gia_ban
        tong_tien_hd += tien_ve
        details_to_create.append(ChiTietHoaDon(
            hoa_don=hd,
            thuc_don=ve_buffet,
            ten_mon_luu_tru=ve_buffet.ten_mon,
            don_gia_luu_tru=ve_buffet.gia_ban,
            so_luong=so_khach,
            thanh_tien=tien_ve,
            thoi_gian_order=checkin_time
        ))

        # Chi tiết: Đồ uống (kích AI Upsell warning)
        if rng.random() < drink_prob:
            drink = thap_bia
            drink_qty = 1
        else:
            drink = nuoc_ngot
            drink_qty = so_khach

        if drink:
            tien_drink = drink_qty * drink.gia_ban
            tong_tien_hd += tien_drink
            details_to_create.append(ChiTietHoaDon(
                hoa_don=hd,
                thuc_don=drink,
                ten_mon_luu_tru=drink.ten_mon,
                don_gia_luu_tru=drink.gia_ban,
                so_luong=drink_qty,
                thanh_tien=tien_drink,
                thoi_gian_order=checkin_time
            ))

        # Chi tiết: Món phụ linh hoạt (Hải sản gọi thêm, món khác, ...)
        if extra_items:
            num_extra = rng.randint(0, 3) # Ngẫu nhiên gọi thêm 0-3 món phụ
            if num_extra > 0:
                chosen_extras = rng.choices(extra_items, k=num_extra)
                for extra in chosen_extras:
                    if drink and extra.id == drink.id:
                        continue # Tránh trùng lặp với món drink đã gọi ở trên
                    
                    extra_qty = rng.randint(1, max(1, so_khach // 2))
                    tien_extra = extra_qty * extra.gia_ban
                    tong_tien_hd += tien_extra
                    
                    details_to_create.append(ChiTietHoaDon(
                        hoa_don=hd,
                        thuc_don=extra,
                        ten_mon_luu_tru=extra.ten_mon,
                        don_gia_luu_tru=extra.gia_ban,
                        so_luong=extra_qty,
                        thanh_tien=tien_extra,
                        thoi_gian_order=checkin_time
                    ))

        # Cập nhật tổng tiền
        hd.khach_can_tra = tong_tien_hd

    return bills_to_create, details_to_create, counter


def seed_ai_data(force_reset=False, status_only=False):
    print("=" * 60)
    print("🤖 POSEIDON AI DATA SEEDER — Incremental Mode")
    print("=" * 60)

    # --- 1. BÀN ĂN ---
    ban_an_list = list(BanAn.objects.exclude(trang_thai='da_xoa'))
    if not ban_an_list:
        print("❌ Không tìm thấy bàn ăn! Hãy tạo bàn ăn trước.")
        return
    print(f"\n📋 Bước 1/5 — Bàn ăn: {len(ban_an_list)} bàn sẵn sàng")

    # --- 2. NHÂN VIÊN ---
    nv_list = []
    for i in range(1, 10):
        nv, _ = NhanVien.objects.get_or_create(
            ma_nv=f"NV{i}", defaults={"ho_ten": f"Nhân viên {i}"}
        )
        nv_list.append(nv)
    today = timezone.now().date()
    print(f"\n👥 Bước 2/5 — Nhân sự & Ca làm hôm nay ({today}):")
    if not status_only:
        setup_staff(today, nv_list)

    # --- 3. THỰC ĐƠN ---
    ve_buffet = ThucDon.objects.filter(loai_mon='goi_buffet').first()
    if not ve_buffet:
        print("❌ Chưa có món 'Gói Buffet' trong Thực đơn!")
        return
    nuoc_ngot = (
        ThucDon.objects.filter(loai_mon='do_uong', ten_mon__icontains='ngọt').first()
        or ThucDon.objects.filter(loai_mon='do_uong').first()
    )
    thap_bia = (
        ThucDon.objects.filter(loai_mon='do_uong', ten_mon__icontains='bia').first()
        or nuoc_ngot
    )
    extra_items = list(ThucDon.objects.exclude(loai_mon='goi_buffet'))
    print(f"\n🍽️  Bước 3/5 — Thực đơn: {ve_buffet.ten_mon} | {len(extra_items)} món phụ")

    # --- 4. KHO ---
    print(f"\n📦 Bước 4/5 — Kho & JIT:")
    if not status_only:
        setup_inventory(today)

    # --- 5. HÓA ĐƠN (Incremental) ---
    print(f"\n🧾 Bước 5/5 — Hóa đơn (window: {DAYS_WINDOW} ngày):")

    if force_reset:
        print("   ⚠️  --reset: Đang xóa toàn bộ hóa đơn AI cũ...")
        ChiTietHoaDon.objects.filter(hoa_don__ghi_chu=AI_DATA_TAG).delete()
        HoaDon.objects.filter(ghi_chu=AI_DATA_TAG).delete()
        print("   ✅ Đã xóa sạch!")

    now = timezone.now()

    # Tìm ID lớn nhất hiện có để tránh trùng
    from django.db.models import Max
    max_id = HoaDon.objects.aggregate(m=Max('id'))['m'] or 99000
    id_counter = max(max_id, 99000)

    total_created_bills   = 0
    total_created_details = 0
    total_skipped_days    = 0

    # Tắt auto_now_add trước khi bulk_create
    HoaDon._meta.get_field('thoi_gian_vao').auto_now_add = False
    ChiTietHoaDon._meta.get_field('thoi_gian_order').auto_now_add = False

    try:
        for i in range(0, DAYS_WINDOW + 1):
            d = now - timedelta(days=i)
            d_date = d.date()

            # Số hóa đơn AI mục tiêu cho ngày này (deterministic)
            target = get_day_target(d_date)

            # Đếm hóa đơn AI đã có trong ngày này
            existing = HoaDon.objects.filter(
                thoi_gian_vao__date=d_date,
                ghi_chu=AI_DATA_TAG
            ).count()

            still_needed = target - existing

            if status_only:
                status = "✅ Đủ" if still_needed <= 0 else f"⚠️  Thiếu {still_needed}"
                print(f"   {d_date} ({'Cuối tuần' if d_date.weekday()>=4 else 'Thường':9s}) | Target={target:3d} | Có={existing:3d} | {status}")
                continue

            if still_needed <= 0:
                total_skipped_days += 1
                # In tóm tắt gọn (tránh spam console)
                if i % 7 == 0:
                    print(f"   ⏭️  {d_date}: Đã đủ {existing} hóa đơn → Bỏ qua")
                continue

            # Tạo phần còn thiếu
            bills, details, id_counter = build_bills_for_day(
                d, i, still_needed, ban_an_list,
                ve_buffet, nuoc_ngot, thap_bia, extra_items, id_counter
            )

            HoaDon.objects.bulk_create(bills, ignore_conflicts=True)
            ChiTietHoaDon.objects.bulk_create(details, ignore_conflicts=True)

            total_created_bills   += len(bills)
            total_created_details += len(details)
            print(f"   ➕ {d_date}: +{len(bills):3d} hóa đơn (target={target}, đã có={existing})")

        # --- Hóa đơn đang phục vụ hôm nay (demo AI kích cầu) ---
        if not status_only and 14 <= now.hour <= 17:
            active_tag = "AI_TEST_DATA_ACTIVE"
            HoaDon.objects.filter(ghi_chu=active_tag).delete()
            active_bills = []
            active_details = []
            for b in range(min(3, len(ban_an_list))):
                id_counter += 1
                hd = HoaDon(
                    ma_hoa_don=f"INV-LIVE-{id_counter}",
                    ban_an=ban_an_list[b],
                    thoi_gian_vao=now,
                    so_khach=2,
                    khach_can_tra=2 * 399000,
                    trang_thai='dang_phuc_vu',
                    ghi_chu=active_tag
                )
                hd.id = id_counter
                ban_an_list[b].trang_thai = 'dang_an'
                ban_an_list[b].save()
                active_bills.append(hd)
                active_details.append(ChiTietHoaDon(
                    hoa_don=hd,
                    thuc_don=ve_buffet,
                    ten_mon_luu_tru=ve_buffet.ten_mon,
                    don_gia_luu_tru=ve_buffet.gia_ban,
                    so_luong=2,
                    thanh_tien=2 * ve_buffet.gia_ban,
                    thoi_gian_order=now
                ))
            HoaDon.objects.bulk_create(active_bills, ignore_conflicts=True)
            ChiTietHoaDon.objects.bulk_create(active_details, ignore_conflicts=True)
            print(f"\n   🟢 Đã tạo {len(active_bills)} hóa đơn đang phục vụ (demo AI kích cầu 14-17h)")

    finally:
        # Luôn bật lại auto_now_add dù có lỗi
        HoaDon._meta.get_field('thoi_gian_vao').auto_now_add = True
        ChiTietHoaDon._meta.get_field('thoi_gian_order').auto_now_add = True

    print("\n" + "=" * 60)
    if status_only:
        print("📊 Chế độ STATUS — Không có gì được tạo.")
    elif total_created_bills == 0 and total_skipped_days > 0:
        print(f"⚡ TẤT CẢ {total_skipped_days + 1} NGÀY ĐÃ ĐỦ — Không cần tạo thêm!")
        print("   → Dữ liệu AI đã sẵn sàng. Vào /ai-analytics/ để xem kết quả.")
    else:
        print(f"🎉 HOÀN TẤT! Đã bổ sung {total_created_bills} hóa đơn & {total_created_details} chi tiết.")
        print(f"   → {total_skipped_days} ngày đã đủ, bỏ qua thành công.")
        print("   → Vào /dashboard/ và /ai-analytics/ để xem kết quả.")
    print("=" * 60)


if __name__ == '__main__':
    args = sys.argv[1:]
    force_reset = '--reset' in args
    status_only = '--status' in args

    if force_reset:
        print("\n⚠️  Chế độ RESET: Toàn bộ hóa đơn AI sẽ bị xóa và tạo lại!\n")

    seed_ai_data(force_reset=force_reset, status_only=status_only)
