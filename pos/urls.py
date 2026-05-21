# File: pos/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # 1. Giao diện chính
    path('pos/', views.pos_view, name='pos'),
    path('qr-menu/', views.customer_menu_view, name='customer_menu'),
    path('payments/', views.payments_view, name='payments'),
    path('invoices/', views.invoice_list, name='invoices'),
    path('export-invoices/', views.export_invoices_csv, name='export_invoices'),

    # 2. APIs dùng cho AJAX của màn hình POS
    path('pos/api/tables/', views.api_load_tables, name='api_load_tables'),
    path('pos/api/order/<int:ban_id>/', views.api_get_order, name='api_get_order'),    
    path('pos/api/add-item/', views.api_update_item, name='api_update_item'),
    path('pos/api/checkout/', views.api_checkout, name='api_checkout'),

    # THÊM DÒNG NÀY CHO TÍNH NĂNG VIP
    path('pos/api/apply-vip/', views.api_apply_vip, name='api_apply_vip'),
    path('pos/api/apply-voucher/', views.api_apply_voucher, name='api_apply_voucher'),

    # 3. APIs dùng cho các màn hình khác
    path('invoices/ajax/detail/<int:pk>/', views.invoice_detail_ajax, name='ajax_invoice_detail'),
    path('pos/api/mark-printing/', views.api_mark_printing, name='api_mark_printing'),
    path('pos/api/unlock-table/', views.api_unlock_table, name='api_unlock_table'),
    path('pos/print-bill/<int:bill_id>/', views.print_bill_view, name='print_bill'),
    path('pos/api/update-note/', views.api_update_note, name='api_update_note'),
    path('pos/api/remove-voucher/', views.api_remove_voucher, name='api_remove_voucher'),
]