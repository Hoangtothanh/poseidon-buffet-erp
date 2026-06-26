from django.urls import path
from . import views

urlpatterns = [
       path('dashboard/', views.dashboard_view, name='dashboard'),
       path('ai-analytics/', views.ai_analytics_view, name='ai_analytics'),
       path('ai-analytics/api/ai-generate-voucher/', views.api_ai_generate_voucher, name='api_ai_generate_voucher'),
]