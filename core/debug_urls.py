from django.urls import path
from django.http import HttpResponse
import traceback

def test_realtime_view(request):
    try:
        from django.utils import timezone
        from ai_analytics.views import get_realtime_data
        
        today = timezone.now().date()
        data = get_realtime_data(today)
        
        res = [
            f"Doanh thu: {data['doanh_thu_hom_nay']}",
            f"Thuc khach: {data['thuc_khach_hom_nay']}",
            f"Tien ve: {data['tien_ve']}",
            f"Tien do uong: {data['tien_do_uong']}",
            f"Tien dich vu: {data['tien_dich_vu']}"
        ]
        return HttpResponse("<br>".join(res))
    except Exception as e:
        return HttpResponse(f"<pre>{traceback.format_exc()}</pre>")

urlpatterns = [
    path('test-real/', test_realtime_view),
]
