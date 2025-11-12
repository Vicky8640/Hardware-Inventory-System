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

from django.contrib import admin
from django.urls import path, include
from inventory.views import CustomLoginView # <-- 1. Import CustomLoginView
from inventory.views import custom_logout_view # <-- 2. Import custom_logout_view

urlpatterns = [
    # Admin is required to be at the top level
    path('admin/', admin.site.urls), 
    
    # App URLs (where your inventory/urls.py is included)
    path('inventory/', include('inventory.urls')), 
    
    # 3. Custom Authentication URLs (OVERRIDING django.contrib.auth.urls)
    path('accounts/login/', CustomLoginView.as_view(), name='login'), # Custom View for Success Message
    path('accounts/logout/', custom_logout_view, name='logout'), # Custom View for Success Message
    
    # 4. Include remaining auth URLs (password reset, etc.)
    path('accounts/', include('django.contrib.auth.urls')), 
]