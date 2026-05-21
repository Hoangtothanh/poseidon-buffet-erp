# File: hrm/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('employees/', views.employees_view, name='employees'),
    path('employees/save/', views.save_employee, name='save_employee'),
    path('employees/delete/<int:emp_id>/', views.delete_employee, name='delete_employee'),
    path('employees/export/', views.export_employees_csv, name='export_employees'),
    
    path('shifts/', views.shifts_view, name='shifts'),
    path('shifts/manage/', views.manage_shift, name='manage_shift'),
    path('shifts/weekly/', views.weekly_shifts_view, name='weekly_shifts'),
]