# File này được giữ lại nhưng không có hoạt động nào (đã huỷ kế hoạch tối ưu).
# Nội dung migration đã bị xoá theo yêu cầu người dùng.
from django.db import migrations


class Migration(migrations.Migration):
    """
    Migration rỗng — không thực hiện thay đổi nào.
    Đã huỷ kế hoạch gộp mo_ta_thoi_tiet + ten_su_kien.
    """

    dependencies = [
        ('ai_analytics', '0002_add_weather_holiday_fields'),
    ]

    operations = []
