import os
import random
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

# Import Models từ tất cả các app
from customers.models import KhachHang
from reception.models import KhuVuc, BanAn, PhieuDatBan, PhienSuDungBan
from menu.models import GoiBuffet, MonBuffet, QuayLine, DoUongDichVu, DanhMuc
from inventory.models import DanhMucNguyenLieu, NhaCungCap, NguyenLieu, PhieuNhapKho, ChiTietNhapKho, PhieuXuatKho, ChiTietXuatKho
from pos.models import HoaDon, ChiTietHoaDon, ThanhToan
from hrm.models import NhanVien, CaLamViec, ChiTietCaLam

def run():
    print("⏳ Đang dọn dẹp dữ liệu cũ (Xóa trắng)...")
    # Xóa theo thứ tự tránh lỗi khóa ngoại
    ChiTietHoaDon.objects.all().delete()
    ThanhToan.objects.all().delete()
    HoaDon.objects.all().delete()
    PhienSuDungBan.objects.all().delete()
    PhieuDatBan.objects.all().delete()
    ChiTietNhapKho.objects.all().delete()
    PhieuNhapKho.objects.all().delete()
    ChiTietXuatKho.objects.all().delete()
    PhieuXuatKho.objects.all().delete()
    NguyenLieu.objects.all().delete()
    NhaCungCap.objects.all().delete()
    DanhMucNguyenLieu.objects.all().delete()
    ChiTietCaLam.objects.all().delete()
    CaLamViec.objects.all().delete()
    NhanVien.objects.all().delete()
    DoUongDichVu.objects.all().delete()
    DanhMuc.objects.all().delete()
    MonBuffet.objects.all().delete()
    QuayLine.objects.all().delete()
    GoiBuffet.objects.all().delete()
    BanAn.objects.all().delete()
    KhuVuc.objects.all().delete()
    KhachHang.objects.all().delete()

    print("🌱 Bắt đầu bơm dữ liệu cho POSEIDON ERP...")
    now = timezone.now()

    # ==========================================
    # 1. TÀI KHOẢN & NHÂN SỰ (HRM)
    # ==========================================
    # Tạo User hệ thống (Thu ngân, Kho, Phục vụ)
    u_thungan, _ = User.objects.get_or_create(username='thungan', defaults={'is_staff': True})
    u_thungan.set_password('123456'); u_thungan.save()
    
    u_kho, _ = User.objects.get_or_create(username='thukho', defaults={'is_staff': True})
    u_kho.set_password('123456'); u_kho.save()

    nv_1 = NhanVien.objects.create(user=u_thungan, ma_nv="NV001", ho_ten="Trần Thu Ngân", chuc_vu="Thu ngân", gioi_tinh="Nữ")
    nv_2 = NhanVien.objects.create(user=u_kho, ma_nv="NV002", ho_ten="Lê Thủ Kho", chuc_vu="Thủ kho", gioi_tinh="Nam")
    print("✅ Đã tạo Nhân sự & Tài khoản")

    # ==========================================
    # 2. KHO HÀNG (INVENTORY)
    # ==========================================
    dm_hs = DanhMucNguyenLieu.objects.create(ten_danh_muc="Hải sản tươi sống")
    dm_rau = DanhMucNguyenLieu.objects.create(ten_danh_muc="Rau củ quả")
    
    ncc_bien = NhaCungCap.objects.create(ten_ncc="Vựa Hải Sản Đại Dương", nguoi_lien_he="Anh Hải", so_dien_thoai="0999888777")
    
    nl_1 = NguyenLieu.objects.create(ten_nguyen_lieu="Tôm sú sống", danh_muc=dm_hs, don_vi_tinh="Kg", ton_kho=50, muc_canh_bao=10, don_gia_trung_binh=250000)
    nl_2 = NguyenLieu.objects.create(ten_nguyen_lieu="Cá Hồi NaUy", danh_muc=dm_hs, don_vi_tinh="Kg", ton_kho=5, muc_canh_bao=10, don_gia_trung_binh=450000) # Tồn thấp để test AI cảnh báo
    nl_3 = NguyenLieu.objects.create(ten_nguyen_lieu="Xà lách", danh_muc=dm_rau, don_vi_tinh="Kg", ton_kho=20, don_gia_trung_binh=30000)
    print("✅ Đã tạo Dữ liệu Kho")

    # ==========================================
    # 3. KHÁCH HÀNG (CRM)
    # ==========================================
    kh_1 = KhachHang.objects.create(ho_ten="Nguyễn Phú Vượng", so_dien_thoai="0901234567", diem_tich_luy=150)
    kh_2 = KhachHang.objects.create(ho_ten="Chị Mai VIP", so_dien_thoai="0912345678", diem_tich_luy=1500)
    kh_vanglai = KhachHang.objects.create(ho_ten="Khách Vãng Lai", so_dien_thoai="0000000000", diem_tich_luy=0)
    print("✅ Đã tạo Khách hàng")

    # ==========================================
    # 4. KHÔNG GIAN BÀN (RECEPTION)
    # ==========================================
    kv_sanh = KhuVuc.objects.create(ten_khu_vuc="Tầng 1 - Sảnh chính")
    kv_vip = KhuVuc.objects.create(ten_khu_vuc="Tầng 2 - Phòng VIP")
    
    ban_1 = BanAn.objects.create(ten_ban="Bàn 101", so_ghe=4, khu_vuc=kv_sanh, trang_thai='dang_an') # Sẽ gán khách
    ban_2 = BanAn.objects.create(ten_ban="Bàn 102", so_ghe=4, khu_vuc=kv_sanh, trang_thai='da_dat')  # Sẽ gán đặt trước
    ban_3 = BanAn.objects.create(ten_ban="Bàn 103", so_ghe=6, khu_vuc=kv_sanh, trang_thai='trong')
    ban_vip = BanAn.objects.create(ten_ban="VIP 01", so_ghe=10, khu_vuc=kv_vip, trang_thai='cho_thanh_toan')
    print("✅ Đã tạo Không gian & Sơ đồ bàn")

    # ==========================================
    # 5. THỰC ĐƠN & QUẦY LINE (CATALOG)
    # ==========================================
    goi_thuong = GoiBuffet.objects.create(ten_goi="Buffet Poseidon 359K", gia_ban=359000, trang_thai=True)
    goi_vip = GoiBuffet.objects.create(ten_goi="Buffet Poseidon VIP 459K", gia_ban=459000, trang_thai=True)

    ql_haisan = QuayLine.objects.create(ma_quay="haisan", ten_quay="Quầy Hải Sản", loai_icon="bi-water")
    ql_nuong = QuayLine.objects.create(ma_quay="nuong", ten_quay="Quầy Nướng BBQ", loai_icon="bi-fire")
    
    MonBuffet.objects.create(ma_mon="M01", ten_mon="Hàu nướng mỡ hành", phan_loai="hai_san", vi_tri_line=ql_haisan)
    MonBuffet.objects.create(ma_mon="M02", ten_mon="Ba chỉ bò Mỹ", phan_loai="mon_chinh", vi_tri_line=ql_nuong)

    dm_nuoc = DanhMuc.objects.create(ten_danh_muc="Đồ uống & Bia", icon="bi-cup-straw")
    du_1 = DoUongDichVu.objects.create(ten_mon="Bia Tiger", ma_sku="BIA01", danh_muc=dm_nuoc, gia_ban=35000, gia_von=18000, con_hang=True)
    du_2 = DoUongDichVu.objects.create(ten_mon="Coca Cola", ma_sku="NC01", danh_muc=dm_nuoc, gia_ban=25000, gia_von=10000, con_hang=True)
    print("✅ Đã tạo Thực đơn, Quầy Line & Đồ uống")

    # ==========================================
    # 6. MÔ PHỎNG VẬN HÀNH: ĐẶT BÀN & PHIÊN ĂN
    # ==========================================
    # 6.1 Bàn 102: Khách Đặt Trước (Chưa đến)
    phieu_dat = PhieuDatBan.objects.create(khach_hang=kh_1, ban=ban_2, thoi_gian_den=now + timedelta(hours=2), so_nguoi=4, trang_thai='da_xac_nhan', ghi_chu="Kỷ niệm sinh nhật")

    # 6.2 Bàn 101: Khách Vãng lai Đang Ăn
    phien_101 = PhienSuDungBan.objects.create(ban=ban_1, khach_hang=kh_vanglai, thoi_gian_vao=now - timedelta(minutes=45), so_khach_thuc_te=2, trang_thai='dang_phuc_vu')
    
    # 6.3 Bàn VIP 01: Khách VIP Đang Chờ Thanh Toán
    phien_vip = PhienSuDungBan.objects.create(ban=ban_vip, khach_hang=kh_2, thoi_gian_vao=now - timedelta(hours=2), so_khach_thuc_te=8, trang_thai='dang_phuc_vu') # Trạng thái bàn là cho_thanh_toan
    print("✅ Đã tạo Phiên sử dụng bàn & Đặt bàn")

    # ==========================================
    # 7. BÁN HÀNG (POS & INVOICE)
    # ==========================================
    # Hóa đơn cho Bàn 101 (Đang ăn, chưa thanh toán)
    hd_101 = HoaDon.objects.create(
        phien_su_dung=phien_101, ban_an=ban_1, khach_hang=kh_vanglai, nhan_vien=u_thungan,
        so_khach=2, tong_tien_hang=718000, khach_can_tra=718000, trang_thai='dang_phuc_vu'
    )
    ChiTietHoaDon.objects.create(hoa_don=hd_101, goi_buffet=goi_thuong, ten_mon_luu_tru="Buffet Poseidon 359K", don_gia_luu_tru=359000, so_luong=2, thanh_tien=718000)

    # Hóa đơn cho Bàn VIP (Chờ thanh toán)
    tong_tien_vip = (8 * 459000) + (10 * 35000) # 8 vé VIP + 10 lon Tiger
    hd_vip = HoaDon.objects.create(
        phien_su_dung=phien_vip, ban_an=ban_vip, khach_hang=kh_2, nhan_vien=u_thungan,
        so_khach=8, tong_tien_hang=tong_tien_vip, khach_can_tra=tong_tien_vip, trang_thai='dang_phuc_vu'
    )
    ChiTietHoaDon.objects.create(hoa_don=hd_vip, goi_buffet=goi_vip, ten_mon_luu_tru="Buffet Poseidon VIP 459K", don_gia_luu_tru=459000, so_luong=8, thanh_tien=(8*459000))
    ChiTietHoaDon.objects.create(hoa_don=hd_vip, do_uong=du_1, ten_mon_luu_tru="Bia Tiger", don_gia_luu_tru=35000, so_luong=10, thanh_tien=350000)
    print("✅ Đã tạo Hóa đơn (POS) & Chi tiết order")

    print("\n🎉 HOÀN TẤT TẤT CẢ! HỆ THỐNG ĐÃ CÓ DATA ĐỂ CHẠY!")