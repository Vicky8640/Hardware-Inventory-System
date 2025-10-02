"""
URL configuration for hms_core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# hms_core/urls.py
# hms_project/hms_core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    # Redirect the base URL (http://127.0.0.1:8000/) to the asset list view after login
    path('', lambda request: redirect('asset_list'), name='home'), 
    
    # Django Admin site
    path('admin/', admin.site.urls),
    
    # Include all URLs from our 'inventory' application
    path('inventory/', include('inventory.urls')), 
    
    # Include built-in Django authentication URLs (for /accounts/login/, /accounts/logout/, etc.)
    path('accounts/', include('django.contrib.auth.urls')), 
]