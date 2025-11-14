# hms_project/inventory/urls.py - FINAL CLEANED VERSION

from django.urls import path # <-- Only need path here
from . import views 

urlpatterns = [
    # 1. Asset List View (Main Inventory Page)
    path('', views.asset_list_view, name='asset_list'), 
    
    # 2. Add Asset View (Mass Input Form)
    path('add/', views.add_asset_view, name='add_asset'), 
    
    # 3. Asset Detail View (Display, Maintenance, and Sale Forms)
    path('asset/<int:asset_pk>/', views.asset_detail_view, name='asset_detail'),
    path('asset/edit/<int:asset_pk>/', views.edit_asset_view, name='edit_asset'), 
    
    # 4. Update Status/Sale Logic (POST submission from Detail View)
    path('asset/<int:asset_pk>/update_status/', 
         views.update_asset_status_view, 
         name='update_asset_status'), 
    
    # 5. Maintenance Log Submission
    path('asset/<int:asset_pk>/add_log/', 
         views.add_maintenance_log_view, 
         name='add_maintenance_log'),
         
    # --- BULK SALE (Same Type) ---
    path('sale/bulk/', views.bulk_sale_view, name='bulk_sale'), 

    # --- MIXED-ITEM SALE WORKFLOW ---
    path('sale/mixed/start/', views.start_mixed_sale_view, name='start_mixed_sale'), 
    path('sale/mixed/finalize/', views.finalize_mixed_sale_view, name='finalize_mixed_sale'), 
#     path('sale/mixed/remove/<int:asset_pk>/', views.remove_from_mixed_sale_view, name='remove_from_mixed_sale'), 

    # --- AJAX CART ENDPOINT ---
    path('sale/mixed/add_one/', views.add_to_mixed_sale, name='add_to_mixed_sale'), 
    path('sale/mixed/remove/', views.remove_from_mixed_sale, name='remove_from_mixed_sale'),    # NOTE: AUTH PATHS (login/logout) MUST BE REMOVED FROM HERE
    path('sales/dashboard/', views.sales_dashboard_view, name='sales_dashboard'),
    path('sales/export/', views.export_sales_data_view, name='export_sales_data'), # <-- ADD THIS
    path('types/', views.asset_type_list_view, name='asset_type_list'), # <-- ADD THIS
]