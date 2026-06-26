from django.urls import path
from . import views

urlpatterns = [
    path('settings/', views.settings_view, name='settings'),
    path('settings/general/', views.settings_general, name='settings_general'),
    path('settings/integrations/', views.settings_integrations, name='settings_integrations'), # <--- Fix lỗi của bạn ở đây
    path('settings/ai/', views.settings_ai, name='settings_ai'),
    
    path('settings/permissions/', views.settings_permissions, name='settings_permissions'),
    path('settings/roles/create/', views.settings_create_role, name='settings_create_role'),
    path('settings/roles/delete/', views.settings_delete_role, name='settings_delete_role'),
    
    path('settings/backup/', views.settings_backup, name='settings_backup'),
    path('settings/seed-today/', views.settings_seed_data_today, name='settings_seed_data_today'),
]