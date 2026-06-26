import os
import random
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

# Import Models từ tất cả các app
from customers.models import KhachHang
from reception.models import BanAn, PhieuDatBan
from menu.models import ThucDon
from inventory.models import NhaCungCap, NguyenLieu, PhieuKho, ChiTietPhieuKho
from pos.models import HoaDon, ChiTietHoaDon
from hrm.models import NhanVien, CaLamViec

def run():
    print("⏳ Đang dọn dẹp dữ liệu cũ (Xóa trắng)...")
    ChiTietHoaDon.objects.all().delete()
    HoaDon.objects.all().delete()
    PhieuDatBan.objects.all().delete()
    ChiTietPhieuKho.objects.all().delete()
    PhieuKho.objects.all().delete()
    NguyenLieu.objects.all().delete()
    NhaCungCap.objects.all().delete()
    CaLamViec.objects.all().delete()
    NhanVien.objects.all().delete()
    ThucDon.objects.all().delete()
    BanAn.objects.all().delete()
    KhachHang.objects.all().delete()

    print("🌱 Bắt đầu bơm dữ liệu cho POSEIDON ERP...")
    now = timezone.now()

    # ==========================================
    # 1. TÀI KHOẢN & NHÂN SỰ (HRM)
    # ==========================================
    u_thungan, _ = User.objects.get_or_create(username='thungan', defaults={'is_staff': True})
    u_thungan.set_password('123456'); u_thungan.save()
    
    u_kho, _ = User.objects.get_or_create(username='thukho', defaults={'is_staff': True})
    u_kho.set_password('123456'); u_kho.save()

    nv_1 = NhanVien.objects.create(user=u_thungan, ma_nv="NV001", ho_ten="Trần Thu Ngân", chuc_vu="Thu ngân", so_dien_thoai="0911")
    nv_2 = NhanVien.objects.create(user=u_kho, ma_nv="NV002", ho_ten="Lê Thủ Kho", chuc_vu="Thủ kho", so_dien_thoai="0922")
    print("✅ Đã tạo Nhân sự & Tài khoản")

    # ==========================================
    # 2. KHO HÀNG (INVENTORY)
    # ==========================================
    ncc_bien = NhaCungCap.objects.create(ten_ncc="Vựa Hải Sản Đại Dương", nguoi_lien_he="Anh Hải", so_dien_thoai="0999888777")
    
    nl_1 = NguyenLieu.objects.create(ten_nguyen_lieu="Tôm sú sống", danh_muc="hai_san", don_vi_tinh="Kg", ton_kho=50, muc_canh_bao=10, don_gia_trung_binh=250000)
    nl_2 = NguyenLieu.objects.create(ten_nguyen_lieu="Xà lách", danh_muc="rau_cu", don_vi_tinh="Kg", ton_kho=20, don_gia_trung_binh=30000)
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
    ban_1 = BanAn.objects.create(ten_ban="Bàn 101", so_ghe=4, khu_vuc='Tang_1', trang_thai='dang_an') 
    ban_2 = BanAn.objects.create(ten_ban="Bàn 102", so_ghe=4, khu_vuc='Tang_1', trang_thai='da_dat') 
    ban_3 = BanAn.objects.create(ten_ban="Bàn 103", so_ghe=6, khu_vuc='Tang_1', trang_thai='trong')
    ban_vip = BanAn.objects.create(ten_ban="VIP 01", so_ghe=10, khu_vuc='VIP', trang_thai='cho_thanh_toan')
    print("✅ Đã tạo Sơ đồ bàn")

    # ==========================================
    # 5. THỰC ĐƠN & QUẦY LINE (MENU)
    # ==========================================
    goi_thuong = ThucDon.objects.create(ten_mon="Buffet Poseidon 359K", loai_mon="goi_buffet", danh_muc="buffet", gia_ban=359000, trang_thai=True)
    goi_vip = ThucDon.objects.create(ten_mon="Buffet Poseidon VIP 459K", loai_mon="goi_buffet", danh_muc="buffet", gia_ban=459000, trang_thai=True)
    du_1 = ThucDon.objects.create(ten_mon="Bia Tiger", loai_mon="do_uong", danh_muc="bia_ruou", gia_ban=35000, gia_von=18000)
    print("✅ Đã tạo Thực đơn (Menu)")

    # ==========================================
    # 6. MÔ PHỎNG VẬN HÀNH: ĐẶT BÀN
    # ==========================================
    phieu_dat = PhieuDatBan.objects.create(khach_hang=kh_1, ban=ban_2, thoi_gian_den=now + timedelta(hours=2), so_nguoi=4, trang_thai='da_xac_nhan')

    # ==========================================
    # 7. BÁN HÀNG (POS & INVOICE)
    # ==========================================
    hd_101 = HoaDon.objects.create(
        ban_an=ban_1, khach_hang=kh_vanglai, nhan_vien=u_thungan,
        so_khach=2, tong_tien_hang=718000, khach_can_tra=718000, trang_thai='dang_phuc_vu'
    )
    ChiTietHoaDon.objects.create(hoa_don=hd_101, thuc_don=goi_thuong, ten_mon_luu_tru="Buffet Poseidon 359K", don_gia_luu_tru=359000, so_luong=2, thanh_tien=718000)

    tong_tien_vip = (8 * 459000) + (10 * 35000) 
    hd_vip = HoaDon.objects.create(
        ban_an=ban_vip, khach_hang=kh_2, nhan_vien=u_thungan,
        so_khach=8, tong_tien_hang=tong_tien_vip, khach_can_tra=tong_tien_vip, trang_thai='cho_thanh_toan'
    )
    ChiTietHoaDon.objects.create(hoa_don=hd_vip, thuc_don=goi_vip, ten_mon_luu_tru="Buffet Poseidon VIP 459K", don_gia_luu_tru=459000, so_luong=8, thanh_tien=(8*459000))
    ChiTietHoaDon.objects.create(hoa_don=hd_vip, thuc_don=du_1, ten_mon_luu_tru="Bia Tiger", don_gia_luu_tru=35000, so_luong=10, thanh_tien=350000)
    print("✅ Đã tạo Hóa đơn (POS)")

    print("\n🎉 HOÀN TẤT TẤT CẢ! HỆ THỐNG ĐÃ CÓ DATA CHUẨN 18 CLASS ĐỂ CHẠY!")