from django.urls import path
from . import views

urlpatterns = [
    # Nhóm Khách hàng
    path('customers/', views.customers_view, name='customers'),
    path('customers/save/', views.save_customer, name='save_customer'),
    path('customers/delete/<int:kh_id>/', views.delete_customer, name='delete_customer'),
    path('customers/export/', views.export_customers, name='export_customers'),
    path('customers/import/', views.import_customers, name='import_customers'),
    
    # Nhóm Voucher (Đã làm ở bước trước)
    path('vouchers/', views.vouchers_view, name='vouchers'),
    path('vouchers/save/', views.save_voucher, name='save_voucher'),
    path('vouchers/delete/<int:voucher_id>/', views.delete_voucher, name='delete_voucher'),
]