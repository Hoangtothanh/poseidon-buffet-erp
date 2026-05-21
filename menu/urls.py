from django.urls import path
from . import views

urlpatterns = [
    path('buffet-packages/', views.buffet_packages_view, name='buffet_packages'),
    path('menu/', views.menu_manage_view, name='menu_manage'),
]