from django.urls import path
from . import views

urlpatterns = [
    # 1. Quản lý Nguyên Liệu
    path('ingredients/', views.ingredients_view, name='ingredients'),
    path('ingredients/manage/', views.manage_ingredient, name='manage_ingredient'),
    path('ingredients/import/', views.import_ingredients_csv, name='import_ingredients'),
    path('inventory/ajax/add-category/', views.add_category_ajax, name='ajax_add_category'),
    
    # 2. Nhập Kho
    path('inventory/', views.inventory_list, name='inventory'),
    path('inventory/manage/', views.manage_inventory_in, name='manage_inventory_in'),
    path('inventory/export/', views.export_inventory_csv, name='export_inventory'),

    # 3. Xuất Kho
    path('inventory-out/', views.inventory_outward_view, name='inventory_out'),
    path('inventory-out/manage/', views.manage_inventory_out, name='manage_inventory_out'),
    path('inventory-out/export/', views.export_inventory_outward_csv, name='export_inventory_outward'),
    
    # 4. Tồn Kho
    path('inventory-stock/', views.inventory_stock_view, name='inventory_stock'),
    path('inventory-stock/export/', views.export_inventory_stock_csv, name='export_inventory_stock'),
    path('inventory-stock/ajax/close-period/', views.close_inventory_period_ajax, name='ajax_close_inventory_period'),
    
    # 5. Nhà Cung Cấp
    path('suppliers/', views.suppliers_view, name='suppliers'),
    path('suppliers/manage/', views.manage_supplier, name='manage_supplier'),
    path('suppliers/export/', views.export_suppliers_csv, name='export_suppliers'),
    path('suppliers/import/', views.import_suppliers_csv, name='import_suppliers'),
]