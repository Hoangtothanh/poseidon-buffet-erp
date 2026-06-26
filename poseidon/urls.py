from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),

    # ✅ Redirect URL gốc về trang đăng nhập
    path('', RedirectView.as_view(url='/login/', permanent=False), name='home'),

    # Các app đã được chia nhỏ
    path('', include('accounts.urls')),
    path('', include('core.urls')),
    path('', include('pos.urls')),
    path('', include('reception.urls')),
    path('', include('menu.urls')),
    path('', include('inventory.urls')),
    path('hrm/', include('hrm.urls')),
    path('', include('core.debug_urls')),
    path('', include('reports.urls')),
    path('', include('ai_analytics.urls')),
    path('', include('customers.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)