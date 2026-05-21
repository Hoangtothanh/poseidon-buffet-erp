# 🌊 Poseidon Buffet ERP
## Hệ thống Quản trị Nhà hàng Buffet Hải sản tích hợp AI hỗ trợ ra quyết định sử dụng Django

Poseidon Buffet ERP là hệ thống quản trị nhà hàng buffet hải sản được xây dựng nhằm hỗ trợ doanh nghiệp trong việc quản lý vận hành, bán hàng, kho hàng và phân tích dữ liệu kinh doanh.  
Hệ thống được phát triển theo mô hình ERP hiện đại, tích hợp AI DSS (Decision Support System) nhằm hỗ trợ nhà quản lý đưa ra quyết định nhanh chóng và chính xác hơn.

---

# 📌 Chức năng chính

## 📊 Dashboard & Phân tích dữ liệu thời gian thực
- Thống kê doanh thu theo ngày/tháng/năm
- Biểu đồ trực quan bằng Chart.js
- Theo dõi công suất bàn và lưu lượng khách
- Phân tích hiệu suất hoạt động nhà hàng

## 💻 POS Bán hàng & Sơ đồ bàn động
- Quản lý bán hàng trực tiếp tại quầy
- Mini-map sơ đồ bàn trực quan
- Chuyển bàn, gộp bàn, tách hóa đơn
- Thanh toán QR
- In hóa đơn

## 📅 Quản lý đặt bàn
- Đặt bàn trực tuyến
- Đồng bộ trạng thái bàn theo thời gian thực
- Check-in khách hàng
- Quản lý lịch đặt bàn

## 🍽 Quản lý vé buffet và đồ uống
- Quản lý menu buffet
- Quản lý đồ uống và phụ thu
- Upload hình ảnh sản phẩm
- Phân loại món và giá bán

## 📦 Quản lý kho hàng
- Nhập kho / Xuất kho
- Theo dõi tồn kho
- Quản lý nguyên liệu
- Quản lý nhà cung cấp
- Cảnh báo tồn kho thấp

## 👥 Quản lý khách hàng & CRM
- Quản lý khách hàng thân thiết
- Voucher giảm giá
- Phân hạng VIP
- Theo dõi lịch sử mua hàng

## 🤖 AI DSS - Hệ thống hỗ trợ ra quyết định
- Dự báo lượng khách
- Đề xuất nhập nguyên liệu
- Phân tích doanh thu
- Hỗ trợ quản lý nhân sự
- Phân tích xu hướng tiêu dùng

## 🔐 Phân quyền hệ thống
- Admin
- Quản lý
- Thu ngân
- Nhân viên phục vụ

---

# 🛠 Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Backend | Python, Django |
| Frontend | HTML5, CSS3, JavaScript |
| UI Framework | Bootstrap 5 |
| Database | SQLite / PostgreSQL |
| Charts | Chart.js |
| AI Analytics | Python Data Analysis |
| Version Control | Git & GitHub |

---

## 🚀 Hướng dẫn cài đặt dự án
# 1. Clone project
```bash
git clone https://github.com/Hoangtothanh/poseidon-buffet-erp.git
cd poseidon-buffet-erp
```
# 2. Tạo lập môi trường ảo cô lập thư viện
```bash 
python -m venv venv
```
```bash 
venv\\Scripts\\activate  # Trên Windows
```
```bash 
source venv/bin/activate  # Trên Mac/Linux
```
# 3. Cài đặt toàn bộ các thư viện Python cần thiết
```bash 
pip install -r requirements.txt
```
# 4. Tạo lập cấu trúc bảng trong Database
```bash 
python manage.py makemigrations
```
```bash 
python manage.py migrate
```
# 5. Khởi tạo tài khoản Admin tối cao
```bash 
python manage.py createsuperuser
```
# 6. Kích hoạt Server chạy thử nghiệm
```bash 
python manage.py runserver
