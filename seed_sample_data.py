"""
seed_sample_data.py
===================
Script bổ sung dữ liệu mẫu HOÀN CHỈNH cho hệ thống Poseidon ERP.

DỮ LIỆU ĐƯỢC TẠO:
  1. Vai trò (Django Group) + Phân quyền (QuyenTruyCap) — khớp trang Cài đặt
  2. Tài khoản User + Nhân viên (NhanVien) đầy đủ trường
  3. Khách hàng (KhachHang) đủ hạng thẻ
  4. Nhà cung cấp (NhaCungCap) đa dạng
  5. Nguyên liệu (NguyenLieu) theo từng danh mục
  6. Phiếu Kho nhập/xuất có thời gian thực tế (PhieuKho + ChiTietPhieuKho)
  7. Lịch sử giao dịch (HoaDon + ChiTietHoaDon) ĐỦ thoi_gian_ra, ngay_thanh_toan,
     phuong_thuc_tt — để trang Lịch sử Giao dịch hiển thị đúng

SỬ DỤNG:
  python seed_sample_data.py            → Incremental (bổ sung thiếu, không xóa)
  python seed_sample_data.py --reset    → Xóa và tạo lại toàn bộ
"""

import os
import sys
import django
import random
from datetime import date, timedelta, time
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poseidon.settings')
django.setup()

from django.contrib.auth.models import User, Group
from django.db.models import Max
from customers.models import KhachHang
from hrm.models import NhanVien, CaLamViec
from inventory.models import NguyenLieu, NhaCungCap, PhieuKho, ChiTietPhieuKho
from pos.models import HoaDon, ChiTietHoaDon
from menu.models import ThucDon
from reception.models import BanAn, KhuVuc, PhieuDatBan
from core.models import SystemSetting, QuyenTruyCap


# ==========================================
# 1. VAI TRÒ & PHÂN QUYỀN (khớp trang Cài đặt → v-roles)
# ==========================================
def seed_vai_tro():
    """
    Tạo các Django Group (Vai trò) và bảng QuyenTruyCap tương ứng.
    Các vai trò này sẽ hiển thị đúng trong trang Cài đặt → Vai trò & Phân quyền.
    """
    print("⏳ [1/8] Đang tạo Vai trò & Phân quyền...")

    # Định nghĩa vai trò và ma trận quyền hạn
    # Khớp chính xác với các trường trong core.models.QuyenTruyCap
    VAI_TRO_CONFIG = [
        {
            "name": "Quản lý",
            "quyen": {
                "table_view": True,  "table_edit": True,
                "booking_view": True, "booking_edit": True, "booking_delete": True,
                "pos_view": True,    "pos_edit": True,      "pos_checkout": True,
                "menu_view": True,   "menu_edit": True,     "menu_delete": True,
                "inventory_view": True, "inventory_edit": True, "inventory_delete": True,
                "report_view": True,
                "system_all": True,
            }
        },
        {
            "name": "Thu ngân",
            "quyen": {
                "table_view": True,  "table_edit": True,
                "booking_view": True, "booking_edit": False, "booking_delete": False,
                "pos_view": True,    "pos_edit": True,       "pos_checkout": True,
                "menu_view": True,   "menu_edit": False,     "menu_delete": False,
                "inventory_view": False, "inventory_edit": False, "inventory_delete": False,
                "report_view": False,
                "system_all": False,
            }
        },
        {
            "name": "Phục vụ",
            "quyen": {
                "table_view": True,  "table_edit": True,
                "booking_view": True, "booking_edit": True,  "booking_delete": False,
                "pos_view": True,    "pos_edit": True,       "pos_checkout": False,
                "menu_view": True,   "menu_edit": False,     "menu_delete": False,
                "inventory_view": False, "inventory_edit": False, "inventory_delete": False,
                "report_view": False,
                "system_all": False,
            }
        },
        {
            "name": "Bếp",
            "quyen": {
                "table_view": True,  "table_edit": False,
                "booking_view": False, "booking_edit": False, "booking_delete": False,
                "pos_view": True,    "pos_edit": False,      "pos_checkout": False,
                "menu_view": True,   "menu_edit": False,     "menu_delete": False,
                "inventory_view": True, "inventory_edit": True, "inventory_delete": False,
                "report_view": False,
                "system_all": False,
            }
        },
        {
            "name": "Thủ kho",
            "quyen": {
                "table_view": False, "table_edit": False,
                "booking_view": False, "booking_edit": False, "booking_delete": False,
                "pos_view": False,   "pos_edit": False,      "pos_checkout": False,
                "menu_view": True,   "menu_edit": False,     "menu_delete": False,
                "inventory_view": True, "inventory_edit": True, "inventory_delete": True,
                "report_view": True,
                "system_all": False,
            }
        },
    ]

    created_count = 0
    for cfg in VAI_TRO_CONFIG:
        group, created = Group.objects.get_or_create(name=cfg["name"])
        quyen, _ = QuyenTruyCap.objects.get_or_create(group=group)
        for field, value in cfg["quyen"].items():
            setattr(quyen, field, value)
        quyen.save()
        if created:
            created_count += 1

    print(f"  ✅ Đã tạo {created_count} vai trò mới. Tổng: {Group.objects.count()} vai trò.")


# ==========================================
# 2. TÀI KHOẢN USER + NHÂN VIÊN (HRM)
# ==========================================
def seed_nhan_vien():
    """
    Tạo User + NhanVien đầy đủ tất cả trường, gán đúng Group (vai trò từ DB).
    Tổng 38 nhân viên:
      - 1 Quản lý  | 1 Bếp trưởng | 10 Nhân viên Bếp
      - 20 Phục vụ | 2 Thu ngân   | 2 Lễ tân | 2 Thủ kho
    """
    print("⏳ [2/8] Đang tạo Tài khoản & Nhân viên (38 người)...")

    # Lấy group từ DB (đã tạo ở bước 1)
    g_quanly   = Group.objects.filter(name="Quản lý").first()
    g_thungan  = Group.objects.filter(name="Thu ngân").first()
    g_phucvu   = Group.objects.filter(name="Phục vụ").first()
    g_bep      = Group.objects.filter(name="Bếp").first()
    g_thukho   = Group.objects.filter(name="Thủ kho").first()

    # ──────────────────────────────────────────────────────────────────
    # DANH SÁCH NHÂN VIÊN ĐẦY ĐỦ (38 người)
    # Cột: username | password | is_staff | first_name | last_name
    #       email (gmail) | ma_nv | ho_ten | gioi_tinh | ngay_sinh
    #       so_dien_thoai | dia_chi | chuc_vu | group
    # ──────────────────────────────────────────────────────────────────
    NHAN_VIEN_LIST = [

        # ── QUẢN LÝ (1 người) ─────────────────────────────────────────
        {
            "username": "quanly_01", "password": "Admin@2024!", "is_staff": True,
            "first_name": "Thanh Tùng", "last_name": "Vũ",
            "email": "vuthanhtung.ql@gmail.com",
            "ma_nv": "NV-001", "ho_ten": "Vũ Thanh Tùng",
            "gioi_tinh": "Nam", "ngay_sinh": date(1981, 7, 19),
            "so_dien_thoai": "0901111001",
            "dia_chi": "27 Đinh Tiên Hoàng, Hoàn Kiếm, Hà Nội",
            "chuc_vu": "Quản lý", "group": g_quanly,
        },

        # ── BẾP TRƯỞNG (1 người) ──────────────────────────────────────
        {
            "username": "beptruong_01", "password": "Chef@2024!", "is_staff": False,
            "first_name": "Quang Vinh", "last_name": "Đặng",
            "email": "dangquangvinh.bt@gmail.com",
            "ma_nv": "NV-002", "ho_ten": "Đặng Quang Vinh",
            "gioi_tinh": "Nam", "ngay_sinh": date(1984, 3, 11),
            "so_dien_thoai": "0902222001",
            "dia_chi": "14 Tây Sơn, Đống Đa, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },

        # ── NHÂN VIÊN BẾP (10 người) ──────────────────────────────────
        {
            "username": "bep_01", "password": "Bep@12345", "is_staff": False,
            "first_name": "Thị Cẩm Tú", "last_name": "Nguyễn",
            "email": "nguyencamtu.bep01@gmail.com",
            "ma_nv": "NV-003", "ho_ten": "Nguyễn Thị Cẩm Tú",
            "gioi_tinh": "Nữ", "ngay_sinh": date(1995, 4, 22),
            "so_dien_thoai": "0903333001",
            "dia_chi": "33 Nguyễn Trãi, Thanh Xuân, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },
        {
            "username": "bep_02", "password": "Bep@12345", "is_staff": False,
            "first_name": "Công Minh", "last_name": "Lương",
            "email": "luongcongminh.bep02@gmail.com",
            "ma_nv": "NV-004", "ho_ten": "Lương Công Minh",
            "gioi_tinh": "Nam", "ngay_sinh": date(1993, 10, 5),
            "so_dien_thoai": "0903333002",
            "dia_chi": "62 Giảng Võ, Ba Đình, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },
        {
            "username": "bep_03", "password": "Bep@12345", "is_staff": False,
            "first_name": "Thị Ngọc Trâm", "last_name": "Hoàng",
            "email": "hoangngoctram.bep03@gmail.com",
            "ma_nv": "NV-005", "ho_ten": "Hoàng Thị Ngọc Trâm",
            "gioi_tinh": "Nữ", "ngay_sinh": date(1997, 8, 17),
            "so_dien_thoai": "0903333003",
            "dia_chi": "19 Láng Hạ, Đống Đa, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },
        {
            "username": "bep_04", "password": "Bep@12345", "is_staff": False,
            "first_name": "Nhật Huy", "last_name": "Tô",
            "email": "tonhathuy.bep04@gmail.com",
            "ma_nv": "NV-006", "ho_ten": "Tô Nhật Huy",
            "gioi_tinh": "Nam", "ngay_sinh": date(1998, 1, 28),
            "so_dien_thoai": "0903333004",
            "dia_chi": "88 Kim Giang, Hoàng Mai, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },
        {
            "username": "bep_05", "password": "Bep@12345", "is_staff": False,
            "first_name": "Thị Diễm My", "last_name": "Bùi",
            "email": "buidiezmy.bep05@gmail.com",
            "ma_nv": "NV-007", "ho_ten": "Bùi Thị Diễm My",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2000, 5, 9),
            "so_dien_thoai": "0903333005",
            "dia_chi": "40 Đội Cấn, Ba Đình, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },
        {
            "username": "bep_06", "password": "Bep@12345", "is_staff": False,
            "first_name": "Phú Cường", "last_name": "Đinh",
            "email": "dinhphucuong.bep06@gmail.com",
            "ma_nv": "NV-008", "ho_ten": "Đinh Phú Cường",
            "gioi_tinh": "Nam", "ngay_sinh": date(1996, 12, 3),
            "so_dien_thoai": "0903333006",
            "dia_chi": "56 Hoàng Hoa Thám, Ba Đình, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },
        {
            "username": "bep_07", "password": "Bep@12345", "is_staff": False,
            "first_name": "Thị Lan Anh", "last_name": "Trịnh",
            "email": "trinhlananhbep07@gmail.com",
            "ma_nv": "NV-009", "ho_ten": "Trịnh Thị Lan Anh",
            "gioi_tinh": "Nữ", "ngay_sinh": date(1999, 3, 14),
            "so_dien_thoai": "0903333007",
            "dia_chi": "12 Phùng Hưng, Hà Đông, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },
        {
            "username": "bep_08", "password": "Bep@12345", "is_staff": False,
            "first_name": "Trọng Nghĩa", "last_name": "Lý",
            "email": "lytrongnghia.bep08@gmail.com",
            "ma_nv": "NV-010", "ho_ten": "Lý Trọng Nghĩa",
            "gioi_tinh": "Nam", "ngay_sinh": date(1994, 6, 26),
            "so_dien_thoai": "0903333008",
            "dia_chi": "78 Trần Duy Hưng, Cầu Giấy, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },
        {
            "username": "bep_09", "password": "Bep@12345", "is_staff": False,
            "first_name": "Thị Thanh Hoa", "last_name": "Phan",
            "email": "phanthanhhoa.bep09@gmail.com",
            "ma_nv": "NV-011", "ho_ten": "Phan Thị Thanh Hoa",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2001, 9, 30),
            "so_dien_thoai": "0903333009",
            "dia_chi": "5 Nguyễn Hoàng Tôn, Tây Hồ, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },
        {
            "username": "bep_10", "password": "Bep@12345", "is_staff": False,
            "first_name": "Văn Phúc", "last_name": "Mai",
            "email": "maivanphuc.bep10@gmail.com",
            "ma_nv": "NV-012", "ho_ten": "Mai Văn Phúc",
            "gioi_tinh": "Nam", "ngay_sinh": date(1992, 11, 7),
            "so_dien_thoai": "0903333010",
            "dia_chi": "23 Xuân Diệu, Tây Hồ, Hà Nội",
            "chuc_vu": "Bếp", "group": g_bep,
        },

        # ── NHÂN VIÊN PHỤC VỤ (20 người) ──────────────────────────────
        {
            "username": "phucvu_01", "password": "Srv@12345", "is_staff": False,
            "first_name": "Đức Hải", "last_name": "Trần",
            "email": "tranducchai.pv01@gmail.com",
            "ma_nv": "NV-013", "ho_ten": "Trần Đức Hải",
            "gioi_tinh": "Nam", "ngay_sinh": date(1998, 2, 4),
            "so_dien_thoai": "0904444001",
            "dia_chi": "44 Hàng Bông, Hoàn Kiếm, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_02", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Hồng Vân", "last_name": "Nguyễn",
            "email": "nguyenhongvan.pv02@gmail.com",
            "ma_nv": "NV-014", "ho_ten": "Nguyễn Thị Hồng Vân",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2001, 5, 18),
            "so_dien_thoai": "0904444002",
            "dia_chi": "7 Lương Yên, Hai Bà Trưng, Hà Nội",
            "chuc_vu": "Nhân viên Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_03", "password": "Srv@12345", "is_staff": False,
            "first_name": "Quốc Bảo", "last_name": "Đỗ",
            "email": "doquocbao.pv03@gmail.com",
            "ma_nv": "NV-015", "ho_ten": "Đỗ Quốc Bảo",
            "gioi_tinh": "Nam", "ngay_sinh": date(2000, 7, 25),
            "so_dien_thoai": "0904444003",
            "dia_chi": "91 Bạch Mai, Hai Bà Trưng, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_04", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Yến Nhi", "last_name": "Lê",
            "email": "leyennhi.pv04@gmail.com",
            "ma_nv": "NV-016", "ho_ten": "Lê Thị Yến Nhi",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2002, 10, 12),
            "so_dien_thoai": "0904444004",
            "dia_chi": "38 Khâm Thiên, Đống Đa, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_05", "password": "Srv@12345", "is_staff": False,
            "first_name": "Hùng Cường", "last_name": "Bùi",
            "email": "buihungcuong.pv05@gmail.com",
            "ma_nv": "NV-017", "ho_ten": "Bùi Hùng Cường",
            "gioi_tinh": "Nam", "ngay_sinh": date(1999, 4, 8),
            "so_dien_thoai": "0904444005",
            "dia_chi": "15 Trương Định, Hai Bà Trưng, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_06", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Thu Trang", "last_name": "Cao",
            "email": "caothutrang.pv06@gmail.com",
            "ma_nv": "NV-018", "ho_ten": "Cao Thị Thu Trang",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2003, 1, 20),
            "so_dien_thoai": "0904444006",
            "dia_chi": "29 Tô Hiến Thành, Hai Bà Trưng, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_07", "password": "Srv@12345", "is_staff": False,
            "first_name": "Tiến Dũng", "last_name": "Hoàng",
            "email": "hoangtiendung.pv07@gmail.com",
            "ma_nv": "NV-019", "ho_ten": "Hoàng Tiến Dũng",
            "gioi_tinh": "Nam", "ngay_sinh": date(2000, 11, 3),
            "so_dien_thoai": "0904444007",
            "dia_chi": "72 Hồ Tùng Mậu, Cầu Giấy, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_08", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Phương Liên", "last_name": "Trương",
            "email": "truongphuonglien.pv08@gmail.com",
            "ma_nv": "NV-020", "ho_ten": "Trương Thị Phương Liên",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2002, 6, 15),
            "so_dien_thoai": "0904444008",
            "dia_chi": "50 Xuân Thủy, Cầu Giấy, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_09", "password": "Srv@12345", "is_staff": False,
            "first_name": "Khắc Thịnh", "last_name": "Ngô",
            "email": "ngokhaacthinh.pv09@gmail.com",
            "ma_nv": "NV-021", "ho_ten": "Ngô Khắc Thịnh",
            "gioi_tinh": "Nam", "ngay_sinh": date(1997, 8, 29),
            "so_dien_thoai": "0904444009",
            "dia_chi": "18 Nguyễn Văn Huyên, Cầu Giấy, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_10", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Kim Ngân", "last_name": "Phạm",
            "email": "phamkimngan.pv10@gmail.com",
            "ma_nv": "NV-022", "ho_ten": "Phạm Thị Kim Ngân",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2001, 12, 1),
            "so_dien_thoai": "0904444010",
            "dia_chi": "63 Dịch Vọng, Cầu Giấy, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_11", "password": "Srv@12345", "is_staff": False,
            "first_name": "Trung Kiên", "last_name": "Dương",
            "email": "duongtrungkien.pv11@gmail.com",
            "ma_nv": "NV-023", "ho_ten": "Dương Trung Kiên",
            "gioi_tinh": "Nam", "ngay_sinh": date(1999, 3, 22),
            "so_dien_thoai": "0904444011",
            "dia_chi": "9 Trần Quý Kiên, Cầu Giấy, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_12", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Ngọc Ánh", "last_name": "Vũ",
            "email": "vungocanhpv12@gmail.com",
            "ma_nv": "NV-024", "ho_ten": "Vũ Thị Ngọc Ánh",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2000, 9, 7),
            "so_dien_thoai": "0904444012",
            "dia_chi": "34 Chùa Láng, Đống Đa, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_13", "password": "Srv@12345", "is_staff": False,
            "first_name": "Văn Thiện", "last_name": "Lưu",
            "email": "luuvanthien.pv13@gmail.com",
            "ma_nv": "NV-025", "ho_ten": "Lưu Văn Thiện",
            "gioi_tinh": "Nam", "ngay_sinh": date(2002, 2, 16),
            "so_dien_thoai": "0904444013",
            "dia_chi": "47 Thái Hà, Đống Đa, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_14", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Hải Yến", "last_name": "Đào",
            "email": "daohaiyen.pv14@gmail.com",
            "ma_nv": "NV-026", "ho_ten": "Đào Thị Hải Yến",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2003, 5, 31),
            "so_dien_thoai": "0904444014",
            "dia_chi": "20 Ô Chợ Dừa, Đống Đa, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_15", "password": "Srv@12345", "is_staff": False,
            "first_name": "Minh Trí", "last_name": "Phan",
            "email": "phanminhtri.pv15@gmail.com",
            "ma_nv": "NV-027", "ho_ten": "Phan Minh Trí",
            "gioi_tinh": "Nam", "ngay_sinh": date(1998, 10, 14),
            "so_dien_thoai": "0904444015",
            "dia_chi": "55 Nguyễn Lương Bằng, Đống Đa, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_16", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Bảo Ngọc", "last_name": "Trần",
            "email": "tranbaongoc.pv16@gmail.com",
            "ma_nv": "NV-028", "ho_ten": "Trần Thị Bảo Ngọc",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2001, 7, 6),
            "so_dien_thoai": "0904444016",
            "dia_chi": "16 Linh Lang, Ba Đình, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_17", "password": "Srv@12345", "is_staff": False,
            "first_name": "Việt Hoàng", "last_name": "Hà",
            "email": "haviethoang.pv17@gmail.com",
            "ma_nv": "NV-029", "ho_ten": "Hà Việt Hoàng",
            "gioi_tinh": "Nam", "ngay_sinh": date(2000, 1, 28),
            "so_dien_thoai": "0904444017",
            "dia_chi": "82 Cống Vị, Ba Đình, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_18", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Khánh Huyền", "last_name": "Lê",
            "email": "lekhanhhuyen.pv18@gmail.com",
            "ma_nv": "NV-030", "ho_ten": "Lê Thị Khánh Huyền",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2003, 4, 9),
            "so_dien_thoai": "0904444018",
            "dia_chi": "11 Ngọc Hà, Ba Đình, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_19", "password": "Srv@12345", "is_staff": False,
            "first_name": "Anh Tuấn", "last_name": "Đinh",
            "email": "dinhanhtuan.pv19@gmail.com",
            "ma_nv": "NV-031", "ho_ten": "Đinh Anh Tuấn",
            "gioi_tinh": "Nam", "ngay_sinh": date(1997, 6, 23),
            "so_dien_thoai": "0904444019",
            "dia_chi": "37 Đặng Thai Mai, Tây Hồ, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "phucvu_20", "password": "Srv@12345", "is_staff": False,
            "first_name": "Thị Quỳnh Anh", "last_name": "Hồ",
            "email": "hoquynhanh.pv20@gmail.com",
            "ma_nv": "NV-032", "ho_ten": "Hồ Thị Quỳnh Anh",
            "gioi_tinh": "Nữ", "ngay_sinh": date(2002, 8, 2),
            "so_dien_thoai": "0904444020",
            "dia_chi": "60 Quảng An, Tây Hồ, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },

        # ── THU NGÂN (2 người) ────────────────────────────────────────
        {
            "username": "thungan_01", "password": "Cash@12345", "is_staff": False,
            "first_name": "Thị Ngọc Hà", "last_name": "Nguyễn",
            "email": "nguyenngoccha.tn01@gmail.com",
            "ma_nv": "NV-033", "ho_ten": "Nguyễn Thị Ngọc Hà",
            "gioi_tinh": "Nữ", "ngay_sinh": date(1998, 3, 17),
            "so_dien_thoai": "0905555001",
            "dia_chi": "22 Bà Triệu, Hai Bà Trưng, Hà Nội",
            "chuc_vu": "Thu ngân", "group": g_thungan,
        },
        {
            "username": "thungan_02", "password": "Cash@12345", "is_staff": False,
            "first_name": "Minh Hiếu", "last_name": "Lý",
            "email": "lyminhhieu.tn02@gmail.com",
            "ma_nv": "NV-034", "ho_ten": "Lý Minh Hiếu",
            "gioi_tinh": "Nam", "ngay_sinh": date(2000, 11, 24),
            "so_dien_thoai": "0905555002",
            "dia_chi": "53 Phan Bội Châu, Hoàn Kiếm, Hà Nội",
            "chuc_vu": "Thu ngân", "group": g_thungan,
        },

        # ── LỄ TÂN (2 người) ──────────────────────────────────────────
        {
            "username": "letan_01", "password": "Rcpt@12345", "is_staff": False,
            "first_name": "Thị Mỹ Hạnh", "last_name": "Phùng",
            "email": "phungmyhanh.lt01@gmail.com",
            "ma_nv": "NV-035", "ho_ten": "Phùng Thị Mỹ Hạnh",
            "gioi_tinh": "Nữ", "ngay_sinh": date(1999, 7, 11),
            "so_dien_thoai": "0906666001",
            "dia_chi": "8 Hàng Trống, Hoàn Kiếm, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },
        {
            "username": "letan_02", "password": "Rcpt@12345", "is_staff": False,
            "first_name": "Hữu Lộc", "last_name": "Đoàn",
            "email": "doanhuuloc.lt02@gmail.com",
            "ma_nv": "NV-036", "ho_ten": "Đoàn Hữu Lộc",
            "gioi_tinh": "Nam", "ngay_sinh": date(1997, 2, 5),
            "so_dien_thoai": "0906666002",
            "dia_chi": "44 Trần Phú, Hà Đông, Hà Nội",
            "chuc_vu": "Phục vụ", "group": g_phucvu,
        },

        # ── THỦ KHO (2 người) ─────────────────────────────────────────
        {
            "username": "thukho_01", "password": "Kho@12345", "is_staff": False,
            "first_name": "Thị Lan Chi", "last_name": "Vương",
            "email": "vuonglanchi.kho01@gmail.com",
            "ma_nv": "NV-037", "ho_ten": "Vương Thị Lan Chi",
            "gioi_tinh": "Nữ", "ngay_sinh": date(1996, 5, 13),
            "so_dien_thoai": "0907777001",
            "dia_chi": "30 Ngọc Lâm, Long Biên, Hà Nội",
            "chuc_vu": "Thủ kho", "group": g_thukho,
        },
        {
            "username": "thukho_02", "password": "Kho@12345", "is_staff": False,
            "first_name": "Đình Toàn", "last_name": "Ngô",
            "email": "ngodinhtooan.kho02@gmail.com",
            "ma_nv": "NV-038", "ho_ten": "Ngô Đình Toàn",
            "gioi_tinh": "Nam", "ngay_sinh": date(1994, 10, 20),
            "so_dien_thoai": "0907777002",
            "dia_chi": "17 Gia Quất, Long Biên, Hà Nội",
            "chuc_vu": "Thủ kho", "group": g_thukho,
        },
    ]
    # ──────────────────────────────────────────────────────────────────

    created_count = 0
    skipped_count = 0
    for data in NHAN_VIEN_LIST:
        # Bỏ qua nếu mã NV đã tồn tại
        if NhanVien.objects.filter(ma_nv=data["ma_nv"]).exists():
            skipped_count += 1
            continue

        # Tạo hoặc lấy User Django
        user, u_created = User.objects.get_or_create(username=data["username"])
        if u_created:
            user.set_password(data["password"])
            user.is_staff = data["is_staff"]
            user.first_name = data["first_name"]
            user.last_name  = data["last_name"]
            user.email      = data["email"]
            user.save()

        # Kiểm tra User này đã có NhanVien chưa (OneToOne constraint)
        # Trường hợp: User tồn tại từ trước nhưng chưa có hồ sơ NhanVien
        if NhanVien.objects.filter(user=user).exists():
            skipped_count += 1
            continue

        # Gán đúng Group (vai trò phân quyền từ trang Cài đặt)
        if data["group"]:
            user.groups.set([data["group"]])
        else:
            user.groups.clear()

        # Tạo hồ sơ NhanVien đầy đủ mọi trường model cho phép
        NhanVien.objects.create(
            user=user,
            ma_nv=data["ma_nv"],
            ho_ten=data["ho_ten"],
            gioi_tinh=data["gioi_tinh"],
            ngay_sinh=data["ngay_sinh"],
            so_dien_thoai=data["so_dien_thoai"],
            email=data["email"],
            dia_chi=data["dia_chi"],
            chuc_vu=data["chuc_vu"],
        )
        created_count += 1

    print(f"  ✅ Đã tạo {created_count} nhân viên mới. (Bỏ qua {skipped_count} đã tồn tại)")
    print(f"     Phân bổ: 1 Quản lý | 1 Bếp trưởng | 10 Bếp | 20 Phục vụ | 2 Thu ngân | 2 Lễ tân | 2 Thủ kho")


# ==========================================
# 3. KHÁCH HÀNG (CRM)
# ==========================================
def seed_khach_hang():
    """Tạo khách hàng đủ hạng thẻ: Thành viên, Bạc, Vàng, Kim Cương."""
    print("⏳ [3/8] Đang tạo Khách Hàng...")

    KHACH_HANG_LIST = [
        # Hạng Kim Cương (>= 1500 điểm)
        {"ho_ten": "Nguyễn Phú Vượng",    "so_dien_thoai": "0901111001", "email": "vuong@vngroup.vn",     "ngay_sinh": date(1970, 8, 5),  "diem": 2500},
        {"ho_ten": "Trần Thị Bích Liên",  "so_dien_thoai": "0901111002", "email": "lien.tran@gmail.com",  "ngay_sinh": date(1978, 3, 12), "diem": 1850},
        {"ho_ten": "Lê Hùng Dũng",        "so_dien_thoai": "0901111003", "email": "dungle@corp.com",      "ngay_sinh": date(1982, 11, 20),"diem": 3000},
        # Hạng Vàng (500-1499 điểm)
        {"ho_ten": "Phạm Minh Châu",      "so_dien_thoai": "0902222001", "email": "chau.pm@gmail.com",    "ngay_sinh": date(1990, 6, 15), "diem": 1200},
        {"ho_ten": "Hoàng Thị Nga",       "so_dien_thoai": "0902222002", "email": "nga.hthi@yahoo.com",   "ngay_sinh": date(1985, 9, 8),  "diem": 750},
        {"ho_ten": "Đặng Quốc Hưng",     "so_dien_thoai": "0902222003", "email": "hung.dq@gmail.com",    "ngay_sinh": date(1992, 2, 28), "diem": 600},
        {"ho_ten": "Vũ Thị Hoa",          "so_dien_thoai": "0902222004", "email": "hoa.vt@outlook.com",   "ngay_sinh": date(1988, 7, 3),  "diem": 980},
        # Hạng Bạc (200-499 điểm)
        {"ho_ten": "Bùi Thanh Tâm",       "so_dien_thoai": "0903333001", "email": "tam.bt@gmail.com",     "ngay_sinh": date(1995, 4, 17), "diem": 320},
        {"ho_ten": "Đỗ Xuân Lâm",        "so_dien_thoai": "0903333002", "email": "lam.dx@gmail.com",     "ngay_sinh": date(1998, 1, 22), "diem": 450},
        {"ho_ten": "Ngô Thị Hương",      "so_dien_thoai": "0903333003", "email": "huong.ngo@gmail.com",  "ngay_sinh": date(1993, 12, 5), "diem": 280},
        {"ho_ten": "Lý Văn An",           "so_dien_thoai": "0903333004", "email": "an.lv@gmail.com",      "ngay_sinh": date(2000, 5, 9),  "diem": 200},
        # Hạng Thành viên (0-199 điểm)
        {"ho_ten": "Trương Thị Mai",      "so_dien_thoai": "0904444001", "email": "mai.tt@gmail.com",     "ngay_sinh": date(2001, 8, 14), "diem": 50},
        {"ho_ten": "Hồ Văn Bình",        "so_dien_thoai": "0904444002", "email": "binh.hv@gmail.com",    "ngay_sinh": date(1997, 3, 30), "diem": 120},
        {"ho_ten": "Dương Minh Khoa",    "so_dien_thoai": "0904444003", "email": "khoa.dm@gmail.com",    "ngay_sinh": date(1999, 10, 11),"diem": 0},
        {"ho_ten": "Phan Thị Linh",       "so_dien_thoai": "0904444004", "email": "linh.pt@gmail.com",    "ngay_sinh": date(2003, 2, 5),  "diem": 75},
        {"ho_ten": "Cao Hữu Phúc",       "so_dien_thoai": "0904444005", "email": "phuc.ch@gmail.com",    "ngay_sinh": date(2002, 7, 25), "diem": 150},
        # Khách vãng lai (đặt trước không có TK)
        {"ho_ten": "Khách Đoàn 20 Người","so_dien_thoai": "0999000001", "email": None,                   "ngay_sinh": None,              "diem": 0},
        {"ho_ten": "Khách Công Ty ABC",  "so_dien_thoai": "0999000002", "email": "event@abc.vn",         "ngay_sinh": None,              "diem": 0},
    ]

    created_count = 0
    for kh in KHACH_HANG_LIST:
        if not KhachHang.objects.filter(so_dien_thoai=kh["so_dien_thoai"]).exists():
            KhachHang.objects.create(
                ho_ten=kh["ho_ten"],
                so_dien_thoai=kh["so_dien_thoai"],
                email=kh["email"],
                ngay_sinh=kh["ngay_sinh"],
                diem_tich_luy=kh["diem"],
                is_active=True,
            )
            created_count += 1

    print(f"  ✅ Đã tạo {created_count} khách hàng mới.")


# ==========================================
# 4. NHÀ CUNG CẤP
# ==========================================
def seed_nha_cung_cap():
    """Tạo nhà cung cấp nguyên liệu đủ thông tin."""
    print("⏳ [4/8] Đang tạo Nhà Cung Cấp...")

    NCC_LIST = [
        {"ten": "CTY TNHH Hải Sản Hoàng Gia",    "lien_he": "Anh Tuấn",    "sdt": "0988123456", "dia_chi": "Cảng cá Vũng Tàu, BRVT",           "email": "hoanggia@seafood.vn",      "cong_no": 15000000},
        {"ten": "Tổng Kho Bò Mỹ Vạn Phúc",       "lien_he": "Chị Hương",   "sdt": "0912345678", "dia_chi": "KCN Hà Đông, Hà Nội",               "email": "vanphucbeef@gmail.com",    "cong_no": 45000000},
        {"ten": "HTX Nông Nghiệp Sạch Đà Lạt",   "lien_he": "Chú Ba",      "sdt": "0934567890", "dia_chi": "Phường 3, TP Đà Lạt, Lâm Đồng",    "email": "dalatfresh@farm.com",      "cong_no": 5000000},
        {"ten": "Đại Lý Đồ Uống Tân Phát",       "lien_he": "Anh Nam",     "sdt": "0945678123", "dia_chi": "99 Hoàng Mai, Hà Nội",              "email": "tanphatdrinks@yahoo.com",  "cong_no": 0},
        {"ten": "Siêu Thị Gia Vị Châu Á",        "lien_he": "Chị Mai",     "sdt": "0977889900", "dia_chi": "Chợ Lớn, Q5, TP HCM",              "email": "asian.spices@gmail.com",   "cong_no": 1200000},
        {"ten": "Vựa Hải Sản Biển Đông",          "lien_he": "Anh Hưng",   "sdt": "0966778899", "dia_chi": "Hòn Gai, Quảng Ninh",               "email": "biendong@seafood.vn",      "cong_no": 25000000},
        {"ten": "Công Ty Thực Phẩm CP Việt Nam",  "lien_he": "CSKH",        "sdt": "19006454",   "dia_chi": "KCN Biên Hòa 2, Đồng Nai",          "email": "contact@cp.com.vn",        "cong_no": 0},
        {"ten": "HTX Rau Sạch Mộc Châu",          "lien_he": "Bác Tuấn",    "sdt": "0981112233", "dia_chi": "Tiểu khu Chiềng Ve, Sơn La",        "email": "mocchau.farm@gmail.com",   "cong_no": 8500000},
        {"ten": "Đại Lý Đá Sạch Tinh Khiết",     "lien_he": "Anh Long",    "sdt": "0911223344", "dia_chi": "Cầu Giấy, Hà Nội",                  "email": "dasach@gmail.com",         "cong_no": 500000},
        {"ten": "Kho Gia Dụng F&B",               "lien_he": "Chị Ngọc",   "sdt": "0933445566", "dia_chi": "Trâu Quỳ, Gia Lâm, Hà Nội",        "email": "fnb.supplies@gmail.com",   "cong_no": 1500000},
    ]

    created_count = 0
    for n in NCC_LIST:
        if not NhaCungCap.objects.filter(ten_ncc=n["ten"]).exists():
            NhaCungCap.objects.create(
                ten_ncc=n["ten"],
                nguoi_lien_he=n["lien_he"],
                so_dien_thoai=n["sdt"],
                dia_chi=n["dia_chi"],
                email=n["email"],
                cong_no=n["cong_no"],
                trang_thai=True,
            )
            created_count += 1

    print(f"  ✅ Đã tạo {created_count} nhà cung cấp mới.")


# ==========================================
# 5. NGUYÊN LIỆU (KHO)
# ==========================================
def seed_nguyen_lieu():
    """Tạo nguyên liệu đầy đủ theo từng danh mục."""
    print("⏳ [5/8] Đang tạo Nguyên Liệu...")

    NL_LIST = [
        # HẢI SẢN
        {"ten": "Hàu sữa Vân Đồn",          "dm": "hai_san", "dvt": "Kg",   "gia": 45000,  "ton": 150, "min": 50},
        {"ten": "Tôm hùm baby",              "dm": "hai_san", "dvt": "Kg",   "gia": 850000, "ton": 25,  "min": 10},
        {"ten": "Mực trứng Phan Thiết",      "dm": "hai_san", "dvt": "Kg",   "gia": 220000, "ton": 60,  "min": 20},
        {"ten": "Ốc hương",                  "dm": "hai_san", "dvt": "Kg",   "gia": 350000, "ton": 40,  "min": 15},
        {"ten": "Bạch tuộc đại",             "dm": "hai_san", "dvt": "Kg",   "gia": 180000, "ton": 80,  "min": 30},
        {"ten": "Cua Cà Mau loại 1",         "dm": "hai_san", "dvt": "Kg",   "gia": 650000, "ton": 35,  "min": 15},
        {"ten": "Ghẹ xanh",                  "dm": "hai_san", "dvt": "Kg",   "gia": 450000, "ton": 50,  "min": 20},
        {"ten": "Cá hồi Na Uy",              "dm": "hai_san", "dvt": "Kg",   "gia": 520000, "ton": 45,  "min": 15},
        {"ten": "Ngao hai cồi",              "dm": "hai_san", "dvt": "Kg",   "gia": 120000, "ton": 100, "min": 40},
        {"ten": "Sò huyết",                  "dm": "hai_san", "dvt": "Kg",   "gia": 280000, "ton": 60,  "min": 25},
        # THỊT
        {"ten": "Ba chỉ bò Mỹ thái lát",    "dm": "thit",    "dvt": "Kg",   "gia": 185000, "ton": 200, "min": 50},
        {"ten": "Lõi vai bò Úc",             "dm": "thit",    "dvt": "Kg",   "gia": 280000, "ton": 120, "min": 40},
        {"ten": "Sụn heo non",               "dm": "thit",    "dvt": "Kg",   "gia": 150000, "ton": 90,  "min": 30},
        {"ten": "Thăn ngoại bò Úc (Striploin)","dm": "thit", "dvt": "Kg",   "gia": 350000, "ton": 60,  "min": 20},
        {"ten": "Đùi gà góc tư rút xương",  "dm": "thit",    "dvt": "Kg",   "gia": 65000,  "ton": 150, "min": 50},
        {"ten": "Sườn non heo",              "dm": "thit",    "dvt": "Kg",   "gia": 160000, "ton": 100, "min": 30},
        # RAU CỦ
        {"ten": "Nấm kim châm Hàn Quốc",    "dm": "rau_cu",  "dvt": "Túi",  "gia": 12000,  "ton": 500, "min": 100},
        {"ten": "Cải thảo Đà Lạt",          "dm": "rau_cu",  "dvt": "Kg",   "gia": 15000,  "ton": 300, "min": 80},
        {"ten": "Nấm đùi gà",               "dm": "rau_cu",  "dvt": "Kg",   "gia": 45000,  "ton": 80,  "min": 20},
        {"ten": "Ngô ngọt",                  "dm": "rau_cu",  "dvt": "Bắp",  "gia": 8000,   "ton": 400, "min": 100},
        {"ten": "Xà lách cuộn",              "dm": "rau_cu",  "dvt": "Kg",   "gia": 30000,  "ton": 120, "min": 40},
        {"ten": "Cà chua bi",                "dm": "rau_cu",  "dvt": "Kg",   "gia": 40000,  "ton": 80,  "min": 25},
        {"ten": "Kim chi cải thảo Hàn Quốc","dm": "rau_cu",  "dvt": "Kg",   "gia": 60000,  "ton": 100, "min": 30},
        # GIA VỊ
        {"ten": "Sốt Thái chua cay",         "dm": "gia_vi",  "dvt": "Lít",  "gia": 85000,  "ton": 50,  "min": 15},
        {"ten": "Sốt BBQ ướp thịt",          "dm": "gia_vi",  "dvt": "Lít",  "gia": 95000,  "ton": 45,  "min": 15},
        {"ten": "Gia vị lẩu Thái Tomyum",    "dm": "gia_vi",  "dvt": "Hộp",  "gia": 250000, "ton": 60,  "min": 20},
        {"ten": "Nước mắm Nam Ngư 10L",     "dm": "gia_vi",  "dvt": "Can",  "gia": 350000, "ton": 20,  "min": 5},
        {"ten": "Dầu ăn Tường An 20L",      "dm": "gia_vi",  "dvt": "Can",  "gia": 850000, "ton": 15,  "min": 5},
        {"ten": "Đường kính trắng",          "dm": "gia_vi",  "dvt": "Kg",   "gia": 22000,  "ton": 100, "min": 30},
        # KHÁC
        {"ten": "Cồn thạch nấu lẩu",        "dm": "khac",    "dvt": "Thùng","gia": 180000, "ton": 80,  "min": 20},
        {"ten": "Giấy ăn rút",               "dm": "khac",    "dvt": "Bịch", "gia": 15000,  "ton": 500, "min": 100},
        {"ten": "Than hoa không khói",       "dm": "khac",    "dvt": "Kg",   "gia": 18000,  "ton": 300, "min": 100},
        {"ten": "Nước rửa chén Sunlight 10L","dm": "khac",   "dvt": "Can",  "gia": 220000, "ton": 20,  "min": 5},
    ]

    created_count = 0
    for nl in NL_LIST:
        if not NguyenLieu.objects.filter(ten_nguyen_lieu=nl["ten"]).exists():
            NguyenLieu.objects.create(
                ten_nguyen_lieu=nl["ten"],
                danh_muc=nl["dm"],
                don_vi_tinh=nl["dvt"],
                don_gia_trung_binh=nl["gia"],
                ton_kho=nl["ton"],
                muc_canh_bao=nl["min"],
            )
            created_count += 1

    print(f"  ✅ Đã tạo {created_count} nguyên liệu mới.")


# ==========================================
# 6. PHIẾU KHO (NHẬP / XUẤT) — 30 ngày qua
# ==========================================
def seed_phieu_kho():
    """
    Tạo phiếu nhập/xuất kho cho 30 ngày qua.
    Dùng để báo cáo tiêu thụ và biểu đồ kho hiển thị đúng.
    """
    print("⏳ [6/8] Đang tạo Phiếu Kho (30 ngày qua)...")

    ncc_list   = list(NhaCungCap.objects.all())
    nl_list    = list(NguyenLieu.objects.all())
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

    if not nl_list or not ncc_list:
        print("  ⚠️  Không đủ NL/NCC để tạo phiếu kho. Bỏ qua.")
        return

    # Chỉ tạo nếu chưa có phiếu nào trong 30 ngày
    today = timezone.now().date()
    existing = PhieuKho.objects.filter(
        ngay_thuc_hien__date__gte=today - timedelta(days=30)
    ).count()
    if existing > 5:
        print(f"  ⏭️  Đã có {existing} phiếu kho trong 30 ngày. Bỏ qua.")
        return

    rng = random.Random(42)
    created_count = 0

    for i in range(1, 31):
        d = timezone.now() - timedelta(days=i)

        # --- Phiếu NHẬP (mỗi 3 ngày) ---
        if i % 3 == 0:
            ncc = rng.choice(ncc_list)
            pn = PhieuKho.objects.create(
                loai_phieu='nhap',
                nha_cung_cap=ncc,
                nguoi_thuc_hien=admin_user,
                ngay_thuc_hien=d,
                da_thanh_toan=True,
                ghi_chu=f"Nhập hàng định kỳ ngày {d.date().strftime('%d/%m/%Y')}",
            )
            tong_nhap = 0
            chosen_nl = rng.choices(nl_list, k=rng.randint(3, 6))
            for nl in chosen_nl:
                sl = rng.randint(20, 80)
                don_gia = int(nl.don_gia_trung_binh)
                tt = sl * don_gia
                ChiTietPhieuKho.objects.create(
                    phieu=pn,
                    nguyen_lieu=nl,
                    so_luong=sl,
                    don_gia=don_gia,
                    thanh_tien=tt,
                )
                tong_nhap += tt
                nl.ton_kho = float(nl.ton_kho) + sl
                nl.save()
            pn.tong_tien = tong_nhap
            pn.save()
            created_count += 1

        # --- Phiếu XUẤT (mỗi ngày) ---
        px = PhieuKho.objects.create(
            loai_phieu='xuat',
            nguoi_thuc_hien=admin_user,
            ngay_thuc_hien=d,
            da_thanh_toan=True,
            ghi_chu="Xuất nguyên liệu phục vụ bếp" if rng.random() > 0.2 else "Xuất hủy hàng hỏng",
        )
        chosen_nl = rng.choices(nl_list, k=rng.randint(2, 5))
        for nl in chosen_nl:
            sl = rng.randint(5, 25)
            ChiTietPhieuKho.objects.create(
                phieu=px,
                nguyen_lieu=nl,
                so_luong=sl,
                don_gia=0,
                thanh_tien=0,
            )
            nl.ton_kho = max(0, float(nl.ton_kho) - sl)
            nl.save()
        created_count += 1

    print(f"  ✅ Đã tạo {created_count} phiếu kho (nhập + xuất).")


# ==========================================
# 7. LỊCH SỬ GIAO DỊCH — HÓA ĐƠN ĐÃ THANH TOÁN (30 ngày qua)
# ==========================================
def seed_hoa_don():
    """
    Tạo hóa đơn đã thanh toán với ĐẦY ĐỦ trường:
      - thoi_gian_vao (giờ check-in)
      - thoi_gian_ra  (giờ check-out / thanh toán) → bắt buộc để hiển thị đúng
      - ngay_thanh_toan → dùng cho lịch sử giao dịch
      - phuong_thuc_tt  → hiển thị phương thức trên Transaction Log
      - tong_tien_hang, khach_can_tra, so_tien_thu
    """
    print("⏳ [7/8] Đang tạo Lịch sử Hóa đơn (30 ngày qua)...")

    today = timezone.now().date()
    existing = HoaDon.objects.filter(
        trang_thai='da_thanh_toan',
        thoi_gian_vao__date__gte=today - timedelta(days=30)
    ).count()
    if existing > 20:
        print(f"  ⏭️  Đã có {existing} hóa đơn trong 30 ngày. Bỏ qua.")
        return

    ban_list    = list(BanAn.objects.exclude(trang_thai='da_xoa'))
    buffet_list = list(ThucDon.objects.filter(loai_mon='goi_buffet', trang_thai=True))
    drink_list  = list(ThucDon.objects.filter(loai_mon='do_uong', trang_thai=True))
    kh_list     = list(KhachHang.objects.filter(is_active=True))
    nv_list     = list(User.objects.filter(nhanvien__isnull=False))

    if not ban_list or not buffet_list:
        print("  ⚠️  Cần có Bàn ăn và Gói Buffet trước. Bỏ qua.")
        return

    # ─────────────────────────────────────────────────────────────────
    # CHỈ 2 PHƯƠNG THỨC KHỚP VỚI MÁY POS THỰC TẾ:
    #   70% Tiền mặt  |  30% Chuyển khoản QR
    # ─────────────────────────────────────────────────────────────────
    PAYMENT_METHODS  = ['tien_mat', 'chuyen_khoan']
    PAYMENT_WEIGHTS  = [0.70,       0.30]
    HOUR_CHOICES  = [11, 12, 13, 17, 18, 19, 20, 21]
    HOUR_WEIGHTS  = [0.1, 0.25, 0.1, 0.05, 0.15, 0.2, 0.1, 0.05]
    GROUP_CHOICES = [2, 4, 6, 8, 10]
    GROUP_WEIGHTS = [0.3, 0.35, 0.2, 0.1, 0.05]

    rng = random.Random(2024)
    created_count = 0

    # Tắt auto_now_add để tự set thời gian mẫu
    HoaDon._meta.get_field('thoi_gian_vao').auto_now_add = False
    ChiTietHoaDon._meta.get_field('thoi_gian_order').auto_now_add = False

    try:
        for i in range(30, 0, -1):  # Từ 30 ngày trước đến hôm qua
            d_date = today - timedelta(days=i)
            is_weekend = d_date.weekday() >= 4
            num_bills = rng.randint(80, 120) if is_weekend else rng.randint(50, 75)

            for _ in range(num_bills):
                hour = rng.choices(HOUR_CHOICES, weights=HOUR_WEIGHTS, k=1)[0]
                minute = rng.randint(0, 59)
                so_khach = rng.choices(GROUP_CHOICES, weights=GROUP_WEIGHTS, k=1)[0]

                # Thời gian check-in
                checkin_dt = timezone.make_aware(
                    __import__('datetime').datetime(
                        d_date.year, d_date.month, d_date.day,
                        hour, minute, rng.randint(0, 59)
                    )
                )
                # Thời gian check-out = check-in + 1.5–2.5 giờ
                duration_min = rng.randint(90, 150)
                checkout_dt = checkin_dt + timedelta(minutes=duration_min)

                buffet = rng.choice(buffet_list)
                phuong_thuc = rng.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS, k=1)[0]
                nhan_vien = rng.choice(nv_list) if nv_list else None
                khach_hang = rng.choice(kh_list) if rng.random() < 0.4 else None

                # Tính tiền
                tien_buffet = int(buffet.gia_ban) * so_khach
                tong_tien = tien_buffet

                # Đồ uống (40% khả năng gọi)
                drink_details = []
                if drink_list and rng.random() < 0.4:
                    drink = rng.choice(drink_list)
                    sl_drink = rng.randint(1, max(1, so_khach // 2))
                    tien_drink = int(drink.gia_ban) * sl_drink
                    tong_tien += tien_drink
                    drink_details.append((drink, sl_drink, tien_drink))

                hd = HoaDon(
                    ban_an=rng.choice(ban_list),
                    khach_hang=khach_hang,
                    nhan_vien=nhan_vien,
                    thoi_gian_vao=checkin_dt,
                    thoi_gian_ra=checkout_dt,          # ← Bắt buộc cho Transaction Log
                    so_khach=so_khach,
                    tong_tien_hang=tong_tien,
                    chiet_khau=0,
                    vat_phu_thu=0,
                    khach_can_tra=tong_tien,
                    phuong_thuc_tt=phuong_thuc,         # ← Phương thức thanh toán
                    so_tien_thu=tong_tien,
                    ngay_thanh_toan=checkout_dt,         # ← Thời gian giao dịch
                    trang_thai='da_thanh_toan',
                    ghi_chu="SEED_HISTORY",
                )
                hd.save()

                # Chi tiết: Vé buffet
                ChiTietHoaDon.objects.create(
                    hoa_don=hd,
                    thuc_don=buffet,
                    ten_mon_luu_tru=buffet.ten_mon,
                    don_gia_luu_tru=buffet.gia_ban,
                    so_luong=so_khach,
                    thanh_tien=tien_buffet,
                    thoi_gian_order=checkin_dt,
                )

                # Chi tiết: Đồ uống
                for drink, sl_drink, tien_drink in drink_details:
                    ChiTietHoaDon.objects.create(
                        hoa_don=hd,
                        thuc_don=drink,
                        ten_mon_luu_tru=drink.ten_mon,
                        don_gia_luu_tru=drink.gia_ban,
                        so_luong=sl_drink,
                        thanh_tien=tien_drink,
                        thoi_gian_order=checkin_dt + timedelta(minutes=rng.randint(5, 20)),
                    )

                created_count += 1

    finally:
        # Luôn bật lại auto_now_add
        HoaDon._meta.get_field('thoi_gian_vao').auto_now_add = True
        ChiTietHoaDon._meta.get_field('thoi_gian_order').auto_now_add = True

    print(f"  ✅ Đã tạo {created_count} hóa đơn lịch sử.")


# ==========================================
# 8. CA LÀM VIỆC MẪU (HRM)
# ==========================================
def seed_ca_lam_viec():
    """Tạo ca làm việc mẫu cho 7 ngày gần nhất."""
    print("⏳ [8/8] Đang tạo Ca Làm Việc mẫu...")

    nv_list = list(NhanVien.objects.all())
    if not nv_list:
        print("  ⚠️  Chưa có nhân viên. Bỏ qua.")
        return

    today = timezone.now().date()
    created_count = 0

    for i in range(7):
        ngay = today - timedelta(days=i)

        # Ca sáng (service)
        if not CaLamViec.objects.filter(ngay_lam_viec=ngay, loai_ca='morning', bo_phan='service').exists():
            ca = CaLamViec.objects.create(
                ngay_lam_viec=ngay,
                loai_ca='morning',
                bo_phan='service',
                ghi_chu="Ca sáng phục vụ",
            )
            phucvu_nv = [nv for nv in nv_list if 'Phục vụ' in nv.chuc_vu or 'Thu ngân' in nv.chuc_vu]
            ca.nhan_vien.set(phucvu_nv[:4])
            created_count += 1

        # Ca tối (kitchen)
        if not CaLamViec.objects.filter(ngay_lam_viec=ngay, loai_ca='evening', bo_phan='kitchen').exists():
            ca = CaLamViec.objects.create(
                ngay_lam_viec=ngay,
                loai_ca='evening',
                bo_phan='kitchen',
                ghi_chu="Ca tối bếp",
            )
            bep_nv = [nv for nv in nv_list if 'Bếp' in nv.chuc_vu]
            ca.nhan_vien.set(bep_nv)
            created_count += 1

    print(f"  ✅ Đã tạo {created_count} ca làm việc.")


# ==========================================
# MAIN
# ==========================================
def main(force_reset=False):
    print("=" * 60)
    print("🚀 POSEIDON SEED DATA — Đầy đủ & Đồng bộ Cài đặt")
    print("=" * 60)

    if force_reset:
        print("\n⚠️  CHẾ ĐỘ RESET: Xóa dữ liệu seed cũ...")
        # Xóa HoaDon & PhieuKho seed
        HoaDon.objects.filter(ghi_chu="SEED_HISTORY").delete()
        PhieuKho.objects.filter(ghi_chu__icontains="Seed").delete()
        PhieuKho.objects.filter(ghi_chu__icontains="định kỳ").delete()
        # Xóa NhanVien + User được tạo bởi seed (username theo pattern seed)
        seed_usernames = [
            "quanly_01", "beptruong_01",
            *[f"bep_{i:02d}" for i in range(1, 11)],
            *[f"phucvu_{i:02d}" for i in range(1, 21)],
            "thungan_01", "thungan_02",
            "letan_01",   "letan_02",
            "thukho_01",  "thukho_02",
        ]
        # Xóa NhanVien trước (do OneToOne FK → User)
        NhanVien.objects.filter(user__username__in=seed_usernames).delete()
        User.objects.filter(username__in=seed_usernames).delete()
        # Xóa cả nhân viên cũ có tên chung chung dạng "Nhân viên X"
        old_nv = NhanVien.objects.filter(ho_ten__startswith="Nhân viên")
        old_user_ids = list(old_nv.values_list("user_id", flat=True))
        old_nv.delete()
        User.objects.filter(id__in=old_user_ids).delete()
        print("  ✅ Đã xóa NhanVien & User seed cũ (kể cả tên cũ).")
        print("  ✅ Đã xóa HoaDon SEED_HISTORY và PhieuKho cũ.\n")

    seed_vai_tro()
    seed_nhan_vien()
    seed_khach_hang()
    seed_nha_cung_cap()
    seed_nguyen_lieu()
    seed_phieu_kho()
    seed_hoa_don()
    seed_ca_lam_viec()

    print("\n" + "=" * 60)
    print("🎉 HOÀN TẤT! Hệ thống đã có đủ dữ liệu mẫu.")
    print("")
    print("  📊 Kiểm tra ngay:")
    print("     → /settings/#v-roles    : Vai trò & Phân quyền")
    print("     → /hrm/                 : Nhân viên & Ca làm việc")
    print("     → /customers/           : Khách hàng các hạng thẻ")
    print("     → /inventory/           : Kho nguyên liệu")
    print("     → /invoices/            : Lịch sử Giao dịch (có giờ)")
    print("     → /reports/revenue/     : Báo cáo Doanh thu 30 ngày")
    print("=" * 60)


if __name__ == '__main__':
    args = sys.argv[1:]
    force_reset = '--reset' in args
    if force_reset:
        print("\n⚠️  Chế độ --reset: Dữ liệu seed cũ sẽ bị xóa và tạo lại!\n")
    main(force_reset=force_reset)
