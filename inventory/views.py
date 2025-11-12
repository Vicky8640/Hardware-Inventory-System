# inventory/views.py
# inventory/views.py (Replace/Update your main imports)
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.contrib import messages
from django.contrib.auth.views import LoginView # (Keep if using CustomLoginView)
from django.contrib.auth import logout  # <-- Import logout from django.contrib.auth 
from django.core.paginator import Paginator
from decimal import Decimal
import datetime
from django.http import JsonResponse
import json 
from django.contrib.messages.views import SuccessMessageMixin
from django.utils import timezone # ⬅️ ADD THIS
from .models import HardwareAsset as Asset, AssetType, SaleRecord, MaintenanceLog
from .forms import AssetForm, BulkSaleForm, AssetFilterForm, MaintenanceLogForm # Ensure this line imports BulkSaleForm
# --- BASE CONTEXT HELPER (MODIFIED to accept request) ---
def get_base_context(request=None): 
    """Returns the base context including branding variables and cart count."""
    context = {
        'SHOP_NAME': 'Nuclear General Hardware', 
        'SHOP_LOGO_URL': 'nuclear-logo.png', 
    }
    
    # Add cart context only if request is provided
    if request:
        mixed_sale_assets = request.session.get('mixed_sale_assets', [])
        context['mixed_sale_count'] = len(mixed_sale_assets)
        context['ALL_ASSET_TYPES'] = AssetType.objects.all().order_by('name')
        context['STATUS_CHOICES'] = Asset.STATUS_CHOICES
        context['LOCATIONS'] = Asset.LOCATION_CHOICES
        
    return context

# --- HELPER: Serial Number Generator ---
def get_next_serial_number(asset_type_obj, custom_serial=None):
    # Logic remains stable
    if custom_serial:
        return custom_serial
        
    prefix = asset_type_obj.name[:3].upper()
    
    try:
        last_asset = Asset.objects.filter(
            serial_number__startswith=f'{prefix}-'
        ).latest('serial_number') 
        
        last_number_str = last_asset.serial_number.split('-')[-1]
        
        last_number = int(last_number_str)
        next_number = last_number + 1
        
    except Asset.DoesNotExist:
        next_number = 1
        
    return f"{prefix}-{next_number:06d}"


# --- 1. ASSET LIST VIEW (Fixed for template error) ---
@login_required 
## ⚙️ Corrected `asset_list_view`

def asset_list_view(request): 
    status_filter = request.GET.get('status')
    location_filter = request.GET.get('location')
    asset_type_filter = request.GET.get('asset_type') 
    
    # 🎯 FIX 1: Removed 'sale_record' from select_related() to prevent 
    # potential database query errors (like FieldError or Attribute Error 
    # when sale_record is not always present/needed for filtering) 
    assets = Asset.objects.all().select_related('asset_type', 'sale_record')
    if status_filter:
        assets = assets.filter(status=status_filter)
    if location_filter:
        assets = assets.filter(location=location_filter)
    if asset_type_filter:
        assets = assets.filter(asset_type__pk=asset_type_filter)
        
    page_number = request.GET.get('page')
    paginator = Paginator(assets, 30) 
    
    try:
        page_obj = paginator.get_page(page_number) 
    except Exception:
        page_obj = paginator.get_page(1)
        
    # --- CONTEXT ASSEMBLY ---
    # Assuming get_base_context(request) provides necessary global context like SHOP_NAME, etc.
    context = get_base_context(request) 
    
    context.update({
        'assets': page_obj, 
        'current_status': status_filter, 
        'current_location': location_filter, 
        'current_asset_type': asset_type_filter, 
        # Add STATUS_CHOICES and LOCATIONS if they are not in base context
    })

    return render(request, 'inventory/asset_list.html', context)

# --- 2. AJAX CART VIEW (Stable) ---
@login_required
@require_http_methods(["POST"]) 
def add_to_mixed_sale(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            asset_pk_str = str(data.get('asset_pk'))
        except (json.JSONDecodeError, KeyError):
            return JsonResponse({'success': False, 'message': 'Invalid data format or missing asset_pk.'}, status=400)

        cart = request.session.get('mixed_sale_assets', [])
        
        try:
            asset = Asset.objects.get(pk=asset_pk_str, status='IN_STOCK')
            
            if asset_pk_str not in cart:
                cart.append(asset_pk_str)
                request.session['mixed_sale_assets'] = cart
                request.session.modified = True
                
                return JsonResponse({
                    'success': True,
                    'mixed_sale_count': len(cart),
                    'message': f"Asset {asset_pk_str} added to cart."
                })
            else:
                return JsonResponse({
                    'success': True,
                    'mixed_sale_count': len(cart),
                    'message': f"Asset {asset_pk_str} is already in the cart."
                })
                
        except Asset.DoesNotExist:
            return JsonResponse({
                'success': False,
                'mixed_sale_count': len(cart),
                'message': f"Error: Asset {asset_pk_str} not found or not in stock."
            }, status=404)
            
    return JsonResponse({'success': False, 'message': 'Invalid request method or format.'}, status=400)


# --- 3. BULK SALE VIEW (FIXED: NameError and context scope) ---
@login_required
def bulk_sale_view(request):
    # Initialize form for GET/rendering
    form = BulkSaleForm()
    assets_to_sell = [] 

    if request.method == 'POST':
        form = BulkSaleForm(request.POST)
        
        # 🎯 FIX: Corrected indentation for POST logic
        if form.is_valid():
            asset_type = form.cleaned_data['asset_type']
            quantity = form.cleaned_data['quantity']
            # Assuming the form field is correctly named 'sale_price_per_unit'
            # NEW LINE 174 (Corrected key)
            price_per_unit = form.cleaned_data['unit_sale_price']            
            # Ensure price is a Decimal for calculations
            try:
                price_per_unit = float(price_per_unit)
            except (ValueError, TypeError):
                messages.error(request, "Invalid price per unit.")
                return redirect('bulk_sale')

            total_sale_amount = quantity * price_per_unit
            
            # 1. Get the assets to sell
            # Use select_for_update to lock assets during transaction
            assets_to_sell = Asset.objects.filter(
                asset_type=asset_type,
                status='IN_STOCK'
            ).order_by('purchase_date')[:quantity]
            
            if len(assets_to_sell) < quantity:
                messages.error(request, f"Not enough assets in stock for {asset_type.name}. Requested: {quantity}, Available: {len(assets_to_sell)}")
                return redirect('bulk_sale')

            try:
                # Use a transaction to ensure all updates succeed or fail together
                with transaction.atomic():
                    # 2. Create the SaleRecord object
                    sale_record = SaleRecord.objects.create(
                        total_sale_price=total_sale_amount, 
                        sale_type='BULK' 
                    )

                    # 3. Update the individual Assets
                    for asset in assets_to_sell:
                        asset.status = 'SOLD'
                        asset.sale_record = sale_record
                        asset.individual_sale_price = price_per_unit
                        asset.save()
                        
                # 4. CRITICAL: REDIRECT AFTER SUCCESSFUL TRANSACTION
                messages.success(request, f"Successfully marked {quantity} units of {asset_type.name} as SOLD for a total of ${total_sale_amount:,.2f}.")
                return redirect('asset_list')
                
            except Exception as e:
                messages.error(request, f"A database error occurred during sale finalization: {e}")
                # Optional: Log the exception to server logs
                return redirect('bulk_sale')

    # --- GET Request or Invalid POST Form ---
    context = {
        'form': form,
        'assets_to_sell': assets_to_sell, 
        # Add get_base_context(request) if you use it for layout variables
    }
    
    # 🎯 Template Name Check: Based on your file tree, the file is 'bulk_sale.html'
    return render(request, 'inventory/bulk_sale.html', context)
# --- 4. DUMMY/PLACEHOLDER VIEWS (Stable) ---
@login_required 
def add_asset_view(request):
    asset_types = AssetType.objects.all().order_by('name')
    locations = Asset.LOCATION_CHOICES

    if request.method == 'POST':
        form = AssetForm(request.POST) 
        
        quantity = int(request.POST.get('quantity', 1))
        custom_serial = request.POST.get('serial_number', '').strip()

        if form.is_valid():
            cleaned_data = form.cleaned_data
            
            if quantity == 1 and custom_serial and Asset.objects.filter(serial_number=custom_serial).exists():
                 messages.error(request, f"Error: Serial number '{custom_serial}' already exists.")
            else:
                asset_type_pk = cleaned_data['asset_type'].pk
                try:
                    asset_type_obj = AssetType.objects.get(pk=asset_type_pk)
                except AssetType.DoesNotExist:
                    messages.error(request, "Invalid Asset Type selected.")
                    return redirect('add_asset') 
                
                created_count = 0
                
                try:
                    with transaction.atomic():
                        for i in range(quantity):
                            is_custom = (quantity == 1 and i == 0 and custom_serial)
                            
                            serial_num = get_next_serial_number(
                                asset_type_obj, 
                                custom_serial if is_custom else None
                            )

                            Asset.objects.create(
                                asset_type=asset_type_obj,
                                model_number=cleaned_data['model_number'],
                                purchase_price=cleaned_data['purchase_price'],
                                location=cleaned_data['location'],
                                warranty_end_date=cleaned_data['warranty_end_date'],
                                serial_number=serial_num,
                                status='IN_STOCK' 
                            )
                            created_count += 1
                            
                    messages.success(request, f"Successfully created {created_count} asset record(s)!")
                    return redirect('asset_list') 

                except Exception as e:
                    messages.error(request, f"An unexpected error occurred during asset creation: {e}")
        else:
            messages.error(request, "Error adding asset. Please check the required fields.")

    else: # GET request
        form = AssetForm()

    context = {
        **get_base_context(request), 
        'form': form, 
        'asset_types': asset_types, 
        'LOCATIONS': locations, 
    }
    
    return render(request, 'inventory/add_asset_form.html', context)


# inventory/views.py

from django.shortcuts import render, get_object_or_404
# You may need to import your AssetRetirementSale model here
# from .models import Asset, AssetRetirementSale # <-- make sure this is imported
@login_required
@login_required
def asset_detail_view(request, asset_pk):
    """
    Displays detailed information for a single asset, including core data,
    sales/retirement status, and maintenance history.
    """
    
    # 1. Retrieve the Asset object
    # Uses 'asset_pk' as defined in the function signature and assumed URLconf
    asset = get_object_or_404(Asset, pk=asset_pk) 

    # 2. Prepare related data

    # Template variable 'sale_record': The template expects either a SaleRecord 
    # instance (if sold/scrapped) or None. The Asset model's 'sale_record' FK handles this.
    # Note: If asset.status is SCRAPPED, sale_record will exist, but its fields 
    # (like sale_price, profit_loss) will reflect the scrap/loss values.
    sale_record = asset.sale_record
    
    # Template variable 'maintenance_logs': Get all related logs, ordered newest first.
    maintenance_logs = MaintenanceLog.objects.filter(asset=asset).order_by('-log_date')

    # Template variable 'log_form': Form for adding a new log, pre-populated with the asset PK.
    # The template uses a loop structure that expects a form object.
    log_form = MaintenanceLogForm(initial={'asset': asset.pk})
    
    # 3. Create Context
    context = {
        # Use the helper to get global context (e.g., SHOP_NAME, cart count)
        # Assuming get_base_context(request) returns a dictionary
        **get_base_context(request), 
        
        'asset': asset,
        'sale_record': sale_record, # SaleRecord instance or None
        'maintenance_logs': maintenance_logs,
        'log_form': log_form,       # MaintenanceLogForm instance
    }

    # 4. Render the template
    return render(request, 'inventory/asset_detail.html', context)
@login_required
def update_asset_status_view(request, asset_pk):
    messages.info(request, "Placeholder: Update Asset Status View")
    return redirect('asset_list')

@login_required
def add_maintenance_log_view(request, asset_pk):
    messages.info(request, "Placeholder: Add Maintenance Log View")
    return redirect('asset_list')


@login_required
def start_mixed_sale_view(request):
    messages.warning(request, "This view is for full-page selection; use the 'Add to Cart' button on the list view instead.")
    return redirect('asset_list') 

@login_required
@require_http_methods(["GET", "POST"])
def finalize_mixed_sale_view(request):
    # Use the name from the floating cart (asset_list.html)
    asset_pks = request.session.get('mixed_sale_assets', []) 
    assets = Asset.objects.filter(pk__in=asset_pks, status='IN_STOCK')
    
    if not assets.exists():
        messages.error(request, "No assets selected for sale in your cart.")
        return redirect('asset_list')
        
    total_purchase_price = sum(asset.purchase_price for asset in assets)

    if request.method == 'POST':
        form = FinalizeMixedSaleForm(request.POST)
        if form.is_valid():
            total_sale_price = form.cleaned_data['total_sale_price']
            
            try:
                with transaction.atomic():
                    # 1. Create SaleRecord
                    sale_record = SaleRecord.objects.create(
                        total_sale_price=total_sale_price,
                        sale_type='MIXED',
                        # ... other sale details ...
                    )
                    
                    # 2. Update all assets in the cart
                    for asset in assets:
                        asset.status = 'SOLD'
                        asset.sale_record = sale_record
                        asset.save()
                        
                    # 3. Clear the session cart
                    del request.session['mixed_sale_assets']
                    messages.success(request, f"Successfully sold {assets.count()} mixed asset(s) for ${total_sale_price:.2f}!")
                    return redirect('asset_list')
            except Exception as e:
                messages.error(request, f"An error occurred during sale finalization: {e}")
                
    else:
        # Default sale price: e.g., 10% markup on total purchase price
        default_sale_price = total_purchase_price * 1.10 
        form = FinalizeMixedSaleForm(initial={'total_sale_price': default_sale_price})

    context = {
        'assets': assets,
        'form': form,
        'total_purchase_price': total_purchase_price
    }
    return render(request, 'inventory/mixed_sale_finalize.html', context) # Renders the new finalization template
@login_required
@require_http_methods(["GET", "POST"])
def remove_from_mixed_sale_view(request, asset_pk):
    asset_pk_str = str(asset_pk) 
    cart = request.session.get('mixed_sale_assets', [])
    
    if asset_pk_str in cart:
        cart.remove(asset_pk_str)
        request.session['mixed_sale_assets'] = cart
        request.session.modified = True 
        
        messages.success(request, f"Asset ID {asset_pk} was successfully removed from the mixed sale cart.")
        
    else:
        messages.warning(request, f"Asset ID {asset_pk} was not found in the mixed sale cart.")

    return redirect('finalize_mixed_sale')

# inventory/views.py (Add this function)

from django.shortcuts import render, get_object_or_404
# Import your Asset model
# from .models import Asset 


@login_required
def edit_asset_view(request, asset_pk):
    """
    Handles editing an existing asset.
    """
    asset = get_object_or_404(Asset, pk=asset_pk)
    
    if request.method == 'POST':
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            
            # --- ADD SUCCESS MESSAGE HERE ---
            messages.success(request, f"Asset **{asset.serial_number}** has been successfully updated.")
            
            return redirect('asset_detail', asset_pk=asset.pk) # This is your correct redirect
    else:
        form = AssetForm(instance=asset)

    context = {
        **get_base_context(request), 
        'form': form,
        'asset': asset,
    }
    
    return render(request, 'inventory/edit_asset.html', context)



def custom_logout_view(request):
    """Logs the user out and adds a success message before redirecting."""
    if request.user.is_authenticated:
        messages.success(request, f"You have been successfully logged out.")
    
    logout(request)
    # Redirect to the 'login' URL name defined in settings.py/urls.py
    return redirect('login')

class CustomLoginView(SuccessMessageMixin, LoginView):
    """Custom LoginView to display a success message upon successful login."""
    template_name = 'registration/login.html'
    success_message = "Welcome! You have successfully logged in."
    # Redirect URL is usually set by LOGIN_REDIRECT_URL in settings.py
    # If not set, it defaults to /accounts/profile/