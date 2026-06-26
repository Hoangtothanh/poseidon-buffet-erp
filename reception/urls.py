from django.urls import path
from . import views

urlpatterns = [
    path('tables/', views.tables_view, name='tables'),
    path('tables/ajax/clear/<int:ban_id>/', views.clear_table_ajax, name='ajax_clear_table'),
    path('table-zones/', views.table_zones_view, name='table_zones'),
    # ==============================================================
    # 4 ĐƯỜNG DẪN API DÀNH RIÊNG CHO QUẢN LÝ SƠ ĐỒ BÀN (CHUYỂN/GỘP/TÁCH)
    # ==============================================================
    path('api/table-order/<int:ban_id>/', views.api_manager_get_order, name='api_manager_get_order'),
    path('api/table-transfer/', views.api_manager_transfer, name='api_manager_transfer'),
    path('api/table-merge/', views.api_manager_merge, name='api_manager_merge'),
    path('api/table-split/', views.api_manager_split, name='api_manager_split'),

    
    path('bookings/', views.booking_list, name='bookings'),
    path('bookings/ajax/update/<int:pk>/', views.update_booking_status_ajax, name='ajax_update_booking'),
    path('api/search-customer/', views.search_customer, name='search_customer'),
    
    # ========================================================
    # API DÀNH RIÊNG CHO TRANG WEB KHÁCH HÀNG (LANDING PAGE)
    # ========================================================
    path('api/book-table/', views.api_book_table, name='api_book_table'),
    path('bookings/ajax/available-tables/', views.get_available_tables_ajax, name='api_available_tables'),
    
    # 🌟 THÊM DÒNG NÀY ĐỂ KẾT NỐI API XẾP BÀN VÀO MINI MAP 🌟
    path('api/assign-table/', views.api_assign_table, name='api_assign_table'),

    # ========================================================
    # XUẤT / NHẬP DANH SÁCH KHÁCH HÀNG (CSV) -> Đã chuyển sang app customers
    # ========================================================
]