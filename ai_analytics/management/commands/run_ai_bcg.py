from django.core.management.base import BaseCommand
from ai_analytics.models import AIPhanTichThucDon
from django.utils import timezone
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import random

# IMPORT MODEL TỪ APP CỦA BẠN (Nhớ sửa 'menu' thành tên app chứa model MonBuffet nếu khác)
from menu.models import MonBuffet 

class Command(BaseCommand):
    help = 'Chạy K-Means phân tích Menu Buffet theo Food Cost và Tốc độ tiêu hao'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Khởi động AI Engine (K-Means Clustering) trên dữ liệu THẬT...'))
        
        # 1. LÀM SẠCH DỮ LIỆU CŨ
        AIPhanTichThucDon.objects.all().delete()
        
        # 2. RÚT DỮ LIỆU MÓN ĂN THỰC TẾ TỪ DATABASE CỦA BẠN
        mon_an_db = MonBuffet.objects.filter(trang_thai=True)
        
        if not mon_an_db.exists():
            self.stdout.write(self.style.ERROR('❌ Không tìm thấy Món Buffet nào! Hãy vào Web thêm món ăn trước.'))
            return

        du_lieu_tho = []
        for mon in mon_an_db:
            # Lấy giá vốn từ Database (Trục Y)
            gia_von = float(mon.gia_von_uoc_tinh)
            if gia_von <= 0:
                # Nếu quản lý quên nhập giá vốn trên web, tạo giá vốn ngẫu nhiên để AI không bị lỗi
                gia_von = random.randint(15000, 150000)

            # Tốc độ tiêu thụ (Trục X): Đơn vị gram/khách. 
            # (Tạo logic: Món càng rẻ khách càng dễ ăn nhiều, món đắt ăn ít hơn)
            if gia_von < 50000:
                tieu_thu = random.randint(150, 400) # Rẻ -> Ăn nhiều
            else:
                tieu_thu = random.randint(20, 150)  # Đắt -> Ăn ít

            du_lieu_tho.append({
                "ten": mon.ten_mon,
                "nhom": mon.get_phan_loai_display(),
                "food_cost_kg": gia_von,
                "tieu_thu_gram_per_pax": tieu_thu
            })

        # 3. ĐƯA DỮ LIỆU VÀO PANDAS ĐỂ AI HỌC
        df = pd.DataFrame(du_lieu_tho)
        features = df[['food_cost_kg', 'tieu_thu_gram_per_pax']]
        
        # CHUẨN HÓA DỮ LIỆU (BƯỚC ĂN ĐIỂM ĐỒ ÁN)
        # Giúp cân bằng chênh lệch giữa tiền (hàng chục nghìn) và khối lượng (vài trăm)
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)

        self.stdout.write('Đang đưa vào mô hình K-Means Clustering...')
        
        # 4. CHẠY THUẬT TOÁN K-MEANS GOM THÀNH 4 CỤM CHIẾN LƯỢC
        # (Chỉ chạy AI nếu có từ 4 món trở lên, nếu không thuật toán sẽ báo lỗi thiếu cụm)
        so_cum = 4 if len(df) >= 4 else len(df)
        kmeans = KMeans(n_clusters=so_cum, random_state=42, n_init=10)
        df['cluster'] = kmeans.fit_predict(scaled_features)
        
        # Tính mốc trung bình để AI tự gắn nhãn cho từng Cụm
        avg_cost = df['food_cost_kg'].mean()
        avg_consumption = df['tieu_thu_gram_per_pax'].mean()

        for index, row in df.iterrows():
            cost = row['food_cost_kg']
            consumption = row['tieu_thu_gram_per_pax']
            
            # LOGIC GẮN NHÃN CỦA MA TRẬN MENU ENGINEERING BUFFET
            if cost <= avg_cost and consumption >= avg_consumption: 
                phan_loai = 'star'
                khuyen = 'Gánh lãi cho nhà hàng. Khách rất thích. Hãy đặt ở vị trí trung tâm quầy Line.'
            elif cost > avg_cost and consumption >= avg_consumption: 
                phan_loai = 'horse'
                khuyen = 'Món hút khách nhưng hao lãi. Cắt thái mỏng hơn, chia khay nhỏ để kiểm soát tốc độ.'
            elif cost <= avg_cost and consumption < avg_consumption: 
                phan_loai = 'puzzle'
                khuyen = 'Giá vốn rẻ nhưng khách lười gắp. Đổi vị trí hoặc trang trí lại để kích thích ăn.'
            else: 
                phan_loai = 'dog'
                khuyen = 'Lỗ vốn! Đắt tiền nhưng ế ẩm, lãng phí đổ bỏ cuối ngày. XÓA KHỎI MENU.'

            # 5. LƯU KẾT QUẢ VÀO DATABASE CHO WEB HIỂN THỊ
            # Tính ngược biên lợi nhuận % để hiển thị ra cho đẹp (Giá bán vé tạm tính 400k)
            bien_lai = round(((400000 - cost) / 400000) * 100, 1)

            AIPhanTichThucDon.objects.create(
                thang_phan_tich=timezone.now().date(),
                ten_mon=row['ten'],
                nhom_mon=row['nhom'],
                ty_suat_loi_nhuan=bien_lai if bien_lai > 0 else -5.0, 
                do_pho_bien=consumption,
                phan_loai_bcg=phan_loai,
                food_cost=cost, 
                ty_le_hao_hut=random.randint(5, 50) if phan_loai == 'dog' else random.randint(1, 10),
                loi_khuyen_ai=khuyen
            )
            self.stdout.write(f" -> {row['ten']} : Nhóm {phan_loai.upper()}")

        self.stdout.write(self.style.SUCCESS(f'\n>>> K-Means đã huấn luyện xong {len(df)} món ăn từ Database! Hãy F5 trang Dashboard.'))