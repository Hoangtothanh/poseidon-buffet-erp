import os
import sys
import django
import random
from datetime import datetime, timedelta
from django.utils import timezone
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poseidon.settings')
django.setup()

from inventory.models import PhieuKho, ChiTietPhieuKho, NguyenLieu
from django.contrib.auth.models import User

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else timezone.now().strftime('%Y-%m-%d')
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        print("Lỗi: Ngày không đúng định dạng YYYY-MM-DD.")
        print("Sử dụng: python seed_xuat_kho_ngay.py [YYYY-MM-DD]")
        sys.exit(1)

    print(f"🚀 Bắt đầu tạo dữ liệu phiếu xuất kho ngẫu nhiên cho ngày: {target_date}")

    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.first()

    nguyen_lieus = list(NguyenLieu.objects.all())
    if not nguyen_lieus:
        print("❌ Không có nguyên liệu nào trong kho. Hãy thêm dữ liệu nguyên liệu trước!")
        sys.exit(1)

    # 1. Xóa các phiếu xuất cũ trong ngày này (tránh bị rác khi chạy lại nhiều lần)
    old_phieu = PhieuKho.objects.filter(loai_phieu='xuat', ngay_thuc_hien__date=target_date)
    count_old = old_phieu.count()
    if count_old > 0:
        old_phieu.delete()
        print(f"🗑️ Đã xóa {count_old} phiếu xuất cũ trong ngày {target_date}.")

    num_xuat_bep = random.randint(3, 6)
    num_xuat_huy = random.randint(1, 2)
    
    total_created = 0

    def create_phieu(ghi_chu_text):
        nonlocal total_created
        hour = random.randint(8, 21)
        minute = random.randint(0, 59)
        dt = timezone.make_aware(datetime(target_date.year, target_date.month, target_date.day, hour, minute))
        
        phieu = PhieuKho(
            loai_phieu='xuat',
            nguoi_thuc_hien=user,
            ngay_thuc_hien=dt,
            ghi_chu=ghi_chu_text
        )
        phieu.save()
        
        # Override lại ngày_thực_hiện do auto_now có thể ghi đè
        PhieuKho.objects.filter(id=phieu.id).update(ngay_thuc_hien=dt)

        # Chọn ngẫu nhiên 5 đến 20 nguyên liệu để xuất
        num_items = random.randint(5, 20)
        selected_nls = random.sample(nguyen_lieus, min(num_items, len(nguyen_lieus)))
        
        for nl in selected_nls:
            # Kiểm tra nếu nguyên liệu tính bằng đơn vị nguyên (lon, chai...) hoặc thuộc danh mục đồ uống
            is_integer_unit = nl.don_vi_tinh.lower() in ['lon', 'chai', 'thùng', 'bịch', 'can', 'hộp', 'bắp', 'túi'] or nl.danh_muc == 'do_uong'
            
            if is_integer_unit:
                sl = random.randint(1, 15)
                if 'hủy' in ghi_chu_text.lower():
                    sl = random.randint(1, 3)
            else:
                sl = round(random.uniform(1.0, 15.0), 2)
                if 'hủy' in ghi_chu_text.lower():
                    sl = round(random.uniform(0.1, 3.0), 2)
                
            ChiTietPhieuKho.objects.create(
                phieu=phieu,
                nguyen_lieu=nl,
                so_luong=Decimal(str(sl)),
                don_gia=nl.don_gia_trung_binh,
                ghi_chu="AI Auto Seed"
            )
            # Tùy chọn: Có thể cập nhật lại số lượng tồn kho của nguyên liệu
            nl.ton_kho -= Decimal(str(sl))
            if nl.ton_kho < 0: nl.ton_kho = 0
            nl.save(update_fields=['ton_kho'])

        total_created += 1

    # Tạo Phiếu xuất tiêu thụ cho bếp
    for i in range(num_xuat_bep):
        create_phieu(f"Xuất nguyên liệu cho bếp (Ca {i+1})")

    # Tạo Phiếu xuất hủy (để kiểm tra report_consumption có đồ hủy hỏng)
    for i in range(num_xuat_huy):
        create_phieu("Xuất hủy nguyên liệu hỏng/hết hạn")

    print(f"✅ Hoàn tất! Đã tạo {num_xuat_bep} phiếu xuất bếp và {num_xuat_huy} phiếu xuất hủy cho ngày {target_date}.")

if __name__ == "__main__":
    main()
