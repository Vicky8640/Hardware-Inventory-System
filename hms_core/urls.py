# hms_core/urls.py

from django.contrib import admin
from django.urls import path, include
from inventory.views import CustomLoginView
from inventory.views import custom_logout_view

urlpatterns = [
    # 1. Admin is required to be at the top level
    path('admin/', admin.site.urls), 
    
    # 2. CRITICAL FIX: Include Inventory App URLs FIRST (before auth overrides)
    # This ensures 'asset_type_list' and all other app URLs are mapped early.
    path('', include('inventory.urls')), 
    
    # 3. Custom Authentication URLs (OVERRIDING django.contrib.auth.urls)
    path('accounts/login/', CustomLoginView.as_view(), name='login'), # Custom View for Success Message
    path('accounts/logout/', custom_logout_view, name='logout'), # Custom View for Success Message
    
    # 4. Include remaining auth URLs (password reset, etc.) LAST
    path('accounts/', include('django.contrib.auth.urls')), 
    
    # The redundant path is removed/ignored here
]