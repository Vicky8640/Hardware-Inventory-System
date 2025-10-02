# hms_project/inventory/urls.py - CLEANED VERSION

from django.urls import path
from . import views 

urlpatterns = [
    # 1. Asset List View (Main Inventory Page)
    path('', views.asset_list_view, name='asset_list'), 
    
    # 2. Add Asset View (Mass Input Form)
    path('add/', views.add_asset_view, name='add_asset'), 
    
    # 3. Asset Detail View (Display, Maintenance, and Sale Forms)
    path('asset/<int:pk>/', views.asset_detail_view, name='asset_detail'), 
    
    # 4. Update Status/Sale Logic (POST submission from Detail View)
    path('asset/<int:asset_pk>/update_status/', 
         views.update_asset_status_view, 
         name='update_asset_status'), 
         
    # 5. Maintenance Log Submission (POST submission from Detail View)
    path('asset/<int:asset_pk>/add_log/', 
         views.add_maintenance_log_view, 
         name='add_maintenance_log'),
         
    # --- BULK SALE ---
    path('sale/bulk/', views.bulk_sale_view, name='bulk_sale'), 

    # --- MIXED-ITEM SALE ---
    path('sale/mixed/start/', views.start_mixed_sale_view, name='start_mixed_sale'), 
    path('sale/mixed/finalize/', views.finalize_mixed_sale_view, name='finalize_mixed_sale'), 
    
    # --- NEW CART MODIFICATION PATHS (Crucial for buttons) ---
    # Keep these unique names and definitions
    path('sale/mixed/add_one/<int:asset_pk>/', views.add_to_mixed_sale_from_list, name='add_to_mixed_sale_from_list'),
    path('sale/mixed/remove/<int:asset_pk>/', views.remove_from_mixed_sale, name='remove_from_mixed_sale'),
    
    # ... any other UN-DUPLICATED paths ...
]