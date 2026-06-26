# poseidon/views.py
# File này thuộc package cấu hình Django (poseidon/).
# Các view thực tế đã được tách ra các app riêng biệt:
#   - accounts/views.py  → Đăng nhập, đăng xuất, hồ sơ
#   - ai_analytics/views.py → Dashboard & AI
#   - pos/views.py       → Bán hàng (POS)
#   - reception/views.py → Sơ đồ bàn, đặt bàn
#   - menu/views.py      → Thực đơn, gói buffet
#   - inventory/views.py → Kho nguyên liệu
#   - hrm/views.py       → Nhân sự, ca làm việc
#   - reports/views.py   → Báo cáo thống kê
#   - customers/views.py → Khách hàng, voucher
#   - core/views.py      → Cài đặt hệ thống