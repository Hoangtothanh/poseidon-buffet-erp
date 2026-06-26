from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def check_quyen(quyen_name):
    """
    Decorator kiểm tra quyền truy cập của User.
    Nếu User là Superuser -> Cho phép truy cập.
    Nếu User thuộc Group có quyền 'system_all' -> Cho phép truy cập.
    Nếu User thuộc Group có quyền tương ứng với 'quyen_name' -> Cho phép truy cập.
    Ngược lại -> Chuyển hướng về trang chủ và báo lỗi.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
                
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
                
            group = request.user.groups.first()
            if group and hasattr(group, 'quyen'):
                quyen_obj = group.quyen
                if getattr(quyen_obj, 'system_all', False):
                    return view_func(request, *args, **kwargs)
                
                # Kiểm tra quyền cụ thể
                if getattr(quyen_obj, quyen_name, False):
                    return view_func(request, *args, **kwargs)
                    
            messages.error(request, "Lỗi bảo mật: Bạn không có quyền truy cập trang này!")
            return redirect('dashboard')
            
        return _wrapped_view
    return decorator

def has_quyen(user, quyen_name):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    group = user.groups.first()
    if group and hasattr(group, 'quyen'):
        quyen_obj = group.quyen
        if getattr(quyen_obj, 'system_all', False):
            return True
        return getattr(quyen_obj, quyen_name, False)
    return False
