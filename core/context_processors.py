from .models import SystemSetting

def global_settings(request):
    # Lấy cấu hình đầu tiên trong Database đẩy ra toàn bộ các trang web
    setting = SystemSetting.objects.first()
    
    user_quyen = None
    if request.user.is_authenticated:
        group = request.user.groups.first()
        if group and hasattr(group, 'quyen'):
            user_quyen = group.quyen

    return {
        'global_setting': setting,
        'user_quyen': user_quyen
    }