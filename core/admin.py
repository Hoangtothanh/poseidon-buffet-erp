from django.contrib import admin
from .models import SystemSetting, SystemLog

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('restaurant_name', 'hotline', 'vat_tax', 'ai_dataset_window')

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'module', 'level')
    list_filter = ('level', 'module', 'timestamp')
    search_fields = ('action', 'user__username')