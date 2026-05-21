from .models import SystemSetting

def global_settings(request):
    # Lấy cấu hình đầu tiên trong Database đẩy ra toàn bộ các trang web
    setting = SystemSetting.objects.first()
    return {
        'global_setting': setting
    }