from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Các app đã được chia nhỏ
    path('', include('accounts.urls')),
    path('', include('core.urls')),
    path('', include('pos.urls')),
    path('', include('reception.urls')),
    path('', include('menu.urls')),
    path('', include('inventory.urls')),
    path('', include('hrm.urls')),
    path('', include('reports.urls')),
    path('', include('ai_analytics.urls')),
    path('', include('customers.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)