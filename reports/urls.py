from django.urls import path
from . import views

urlpatterns = [
    path('reports/revenue/', views.revenue_report_view, name='report_revenue'),
    path('reports/revenue/export/', views.export_revenue_csv, name='export_revenue'), # <--- Thêm dòng này
    path('reports/consumption/', views.report_consumption_view, name='report_consumption'),
    path('reports/inventory/', views.report_inventory_view, name='report_inventory'),
    path('reports/inventory/export/', views.export_inventory_report_csv, name='export_inventory_report'),
    path('reports/performance/', views.report_performance_view, name='report_performance'),
    path('reports/performance/export/', views.export_performance_report_csv, name='export_performance'),
]