# inventory/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.conf import settings 
# CRITICAL FIX: Ensure 'messages' and 'Decimal' are imported
from django.contrib import messages 
from decimal import Decimal 
from .models import HardwareAsset, AssetType, AssetRetirementSale, MaintenanceLog 
from django.core.paginator import Paginator # <-- NEW IMPORT


# --- Helper for Context (CRITICAL FIX: No arguments allowed) ---
def get_base_context(): 
    """Returns the base context including branding variables."""
    return {
        'SHOP_NAME': getattr(settings, 'SHOP_NAME', 'Hardware Management System'), 
        'SHOP_LOGO_URL': getattr(settings, 'SHOP_LOGO_URL', '/static/logo.png'),
    }

# --- 1. ADD ASSET VIEW ---
@login_required 
@require_http_methods(["GET", "POST"])
def add_asset_view(request):
    
    context = get_base_context() 
    context['asset_types'] = AssetType.objects.all()
    context['LOCATIONS'] = HardwareAsset.LOCATION_CHOICES 

    if request.method == 'GET':
        return render(request, 'inventory/add_asset_form.html', context) 

    elif request.method == 'POST':
        
        # --- 1. RETRIEVE ALL FORM DATA ---
        asset_type_id = request.POST.get('asset_type')
        model_number = request.POST.get('model_number')
        purchase_price_str = request.POST.get('purchase_price')
        location = request.POST.get('location') 
        warranty_end_date = request.POST.get('warranty_end_date')
        single_serial_number = request.POST.get('serial_number', '').strip() 
        print(f"DEBUG: Location received from form: {location}")

        try:
            quantity = int(request.POST.get('quantity', 1))
            purchase_price = Decimal(purchase_price_str)
        except (ValueError, TypeError):
            messages.error(request, "Invalid quantity or price specified.")
            return render(request, 'inventory/add_asset_form.html', context)
        
        # --- 2. VALIDATION AND BUSINESS LOGIC (Main try/except) ---
        if quantity < 1:
            messages.error(request, "Quantity must be 1 or greater.")
            return render(request, 'inventory/add_asset_form.html', context)
            
        try:
            asset_type_obj = AssetType.objects.get(pk=asset_type_id)
            
            with transaction.atomic():
                last_asset = HardwareAsset.objects.order_by('-id').first()
                start_id = (last_asset.id if last_asset else 0) + 1 
                prefix = asset_type_obj.name[:3].upper() 
                
                for i in range(quantity):
                    if quantity > 1 or (quantity == 1 and not single_serial_number):
                        # AUTO-GENERATION
                        current_id_suffix = start_id + i
                        sn_to_use = f"{prefix}-{current_id_suffix:06d}" 
                    else:
                        # USE USER-PROVIDED S/N (only for quantity=1)
                        sn_to_use = single_serial_number
                        
                    if not sn_to_use:
                        raise ValueError("Internal error: Serial number could not be determined.")

                    HardwareAsset.objects.create(
                        asset_type=asset_type_obj,
                        model_number=model_number,
                        serial_number=sn_to_use, 
                        purchase_price=purchase_price,
                        location=location,
                        warranty_end_date=warranty_end_date if warranty_end_date else None,
                    )
            
            # ----------------------------------------------------
            # *** CRITICAL FIX START: SUCCESS MESSAGE AND REDIRECT ***
            # ----------------------------------------------------
            messages.success(request, f"Successfully added {quantity} unit(s) of {asset_type_obj.name}.")
            return redirect('asset_list')
            # ----------------------------------------------------
            # *** CRITICAL FIX END ***
            # ----------------------------------------------------
            
        except AssetType.DoesNotExist:
            messages.error(request, "Invalid Asset Type selected.")
            return render(request, 'inventory/add_asset_form.html', context)
        except IntegrityError:
            messages.error(request, "A Serial Number already exists. Batch creation failed.")
            return render(request, 'inventory/add_asset_form.html', context)
        except ValueError as e:
            messages.error(request, f"Data input error: {e}")
            return render(request, 'inventory/add_asset_form.html', context)
        except Exception as e:
            messages.error(request, f"An unexpected error occurred during submission: {e}")
            return render(request, 'inventory/add_asset_form.html', context)


# --- 2. ASSET LIST VIEW ---
# inventory/views.py


# inventory/views.py (inside asset_list_view)

# inventory/views.py

# ... (Previous code remains the same) ...

# --- 2. ASSET LIST VIEW ---
@login_required 
def asset_list_view(request): 
    """Retrieves and displays the full list of hardware assets."""
    
    # --- 1. INITIALIZE FILTER VARIABLES ---
    # Retrieve query parameters, defaulting to None if not present
    status_filter = request.GET.get('status')
    location_filter = request.GET.get('location')
    asset_type_filter = request.GET.get('asset_type') 
    
    # --- 2. BASE QUERY AND FILTERING ---
    assets = HardwareAsset.objects.all().select_related('asset_type').prefetch_related('sale_record').order_by('id') 

    # Apply Filters
    if status_filter:
        assets = assets.filter(status=status_filter)
    
    if location_filter:
        assets = assets.filter(location=location_filter)
        
    if asset_type_filter:
        assets = assets.filter(asset_type__pk=asset_type_filter)
        
    # --- 3. PAGINATION LOGIC ---
    page_number = request.GET.get('page')
    paginator = Paginator(assets, 30) 
    page_obj = paginator.get_page(page_number) 
    
    # --- 4. CONTEXT ASSEMBLY ---
    
    # Retrieve ALL Asset Types for the filter dropdown
    all_asset_types = AssetType.objects.all().order_by('name') 

    context = {
        # Branding
        'SHOP_NAME': 'Nuclear Hardware',
        'SHOP_LOGO_URL': '/static/inventory/Company_Logos/nuclear-logo-circle-shape-yellow-260nw-2194600213.jpg', 
        
        # Data
        'assets': page_obj, 
        
        # Filter Data for Dropdowns
        'ALL_ASSET_TYPES': all_asset_types, 
        'STATUS_CHOICES': HardwareAsset.STATUS_CHOICES,
        'LOCATIONS': HardwareAsset.LOCATION_CHOICES,    
        
        # Current Filter Selections (to pre-select dropdowns)
        'current_status': status_filter, 
        'current_location': location_filter, 
        'current_asset_type': asset_type_filter, 
    }

    return render(request, 'inventory/asset_list.html', context)
# --- 3. ASSET DETAIL VIEW ---
@login_required
def asset_detail_view(request, pk):
    """
    Displays single asset details, maintenance logs, and the sale/retirement form.
    """
    asset = get_object_or_404(
        # CRITICAL FIX: Select pending_sale_price must be possible if it exists
        HardwareAsset.objects.select_related('asset_type').prefetch_related('maintenancelog_set', 'sale_record'), 
        pk=pk
    )
    
    is_retired = asset.status in ['SOLD', 'SCRAPPED']
    sale_record = None
    
    try:
        if is_retired:
            sale_record = asset.sale_record
    except AssetRetirementSale.DoesNotExist:
        pass

    context = get_base_context()
    context.update({
        'asset': asset,
        'maintenance_logs': asset.maintenancelog_set.all().order_by('-log_date'),
        'is_retired': is_retired,
        'sale_record': sale_record,
        'show_sale_form': asset.status in ['IN_STOCK', 'PENDING_SALE'],
    })
    
    return render(request, 'inventory/asset_detail.html', context)


# --- 4. UPDATE STATUS VIEW (RECONSTRUCTED AND CORRECTED) ---
@login_required
@require_http_methods(["POST"])
def update_asset_status_view(request, asset_pk):
    """
    Handles the transition of an asset status.
    """
    try:
        asset = HardwareAsset.objects.get(pk=asset_pk)
    except HardwareAsset.DoesNotExist:
        messages.error(request, "Asset not found.")
        return redirect('asset_list') 
    
    new_status = request.POST.get('new_status')
    sale_price_str = request.POST.get('sale_price') # Only present for PENDING_SALE

    if new_status == 'PENDING_SALE':
        try:
            # 1. Save the price to the model field 
            sale_price = Decimal(sale_price_str)
            asset.pending_sale_price = sale_price
            asset.status = 'PENDING_SALE'
            asset.save()
            messages.info(request, f"Asset {asset.serial_number} marked as PENDING SALE. Price saved.")
            return redirect('asset_detail', pk=asset_pk) 
        except Exception as e:
            messages.error(request, f"Error saving pending price: {e}")
            return redirect('asset_detail', pk=asset_pk)
            
    # CRITICAL FIX: This 'elif' must be inside the function to prevent SyntaxError
    elif new_status == 'SOLD':
        try:
            # 1. RETRIEVE price from the database field
            sale_price = asset.pending_sale_price
            
            if sale_price is None:
                # If sale price is missing, user didn't go through PENDING_SALE step
                raise ValueError("Sale price was not saved in the PENDING_SALE step.")
            
            # 2. Execute Transaction
            with transaction.atomic():
                # Finalize Status
                asset.status = 'SOLD'
                asset.pending_sale_price = None 
                asset.save()
                
                # 3. Profit Calculation and Record Creation
                cost_basis = asset.purchase_price
                profit_loss = sale_price - cost_basis # Decimal calculation
                
                AssetRetirementSale.objects.create(
                    asset=asset,
                    sale_price=sale_price,
                    cost_basis=cost_basis,
                    profit_loss=profit_loss
                )
            
            # 4. Success Message and Redirect
            messages.success(request, f"Asset {asset.serial_number} sold successfully.")
            return redirect('asset_detail', pk=asset.pk)
            
        except Exception as e:
            messages.error(request, f"Sale Failed: {e}")
            return redirect('asset_detail', pk=asset.pk)
            
    elif new_status == 'SCRAPPED':
        try:
            with transaction.atomic():
                asset.status = 'SCRAPPED'
                asset.pending_sale_price = None # Clear any pending price
                asset.save()
                
                # Create a retirement record with loss
                AssetRetirementSale.objects.create(
                    asset=asset,
                    sale_price=Decimal('0.00'),
                    cost_basis=asset.purchase_price,
                    profit_loss=asset.purchase_price * Decimal('-1.00'), 
                    is_scrapped=True
                )
            messages.warning(request, f"Asset {asset.serial_number} status updated to SCRAPPED (Loss recorded).")
            return redirect('asset_detail', pk=asset_pk) 
        except Exception as e:
            messages.error(request, f"Scrapping failed: {e}")
            return redirect('asset_detail', pk=asset_pk)
    
    # --- FINAL FALLBACK RETURN (Prevents 'returned None' error) ---
    messages.error(request, "Invalid status transition attempted.")
    return redirect('asset_detail', pk=asset_pk)


# --- 5. ADD MAINTENANCE LOG VIEW ---
@login_required
@require_http_methods(["POST"])
def add_maintenance_log_view(request, asset_pk):
    """Handles the form submission to create a new MaintenanceLog record."""
    
    asset = get_object_or_404(HardwareAsset, pk=asset_pk)
    log_date = request.POST.get('log_date')
    log_type = request.POST.get('log_type')
    description = request.POST.get('description')
    cost_str = request.POST.get('cost', '0.00')
    
    try:
        # Use Decimal for cost, not float
        cost = Decimal(cost_str) 
        with transaction.atomic():
            MaintenanceLog.objects.create(
                asset=asset,
                log_date=log_date,
                log_type=log_type,
                description=description,
                cost=cost
            )
        messages.success(request, "Maintenance log added successfully.")
        return redirect('asset_detail', pk=asset_pk)
        
    except Exception as e:
        messages.error(request, f"Error saving maintenance log: {e}")
        return redirect('asset_detail', pk=asset_pk)


# --- 6. BULK SALE VIEW (Fixed for Decimal Conversion) ---
@login_required 
@require_http_methods(["GET", "POST"])
def bulk_sale_view(request):
    
    context = get_base_context() 
    context['asset_types'] = AssetType.objects.all()

    if request.method == 'GET':
        return render(request, 'inventory/bulk_sale_form.html', context)

    elif request.method == 'POST':
        
        asset_type_id = request.POST.get('asset_type')
        
        try:
            quantity = int(request.POST.get('quantity'))
            sale_price_per_unit_str = request.POST.get('sale_price_per_unit')
            if not sale_price_per_unit_str:
                raise ValueError("Sale price per unit is required.")
                
            sale_price_per_unit = Decimal(sale_price_per_unit_str) 
            
        except (ValueError, TypeError) as e:
            context['error'] = f"Invalid quantity or price provided: {e}"
            return render(request, 'inventory/bulk_sale_form.html', context)
        
        if quantity <= 0:
            context['error'] = "Quantity must be greater than zero."
            return render(request, 'inventory/bulk_sale_form.html', context)

        try:
            asset_type_obj = AssetType.objects.get(pk=asset_type_id)
            
            assets_to_sell = HardwareAsset.objects.filter(
                asset_type=asset_type_obj, 
                status='IN_STOCK'
            ).order_by('purchase_date')[:quantity] 
            
            if assets_to_sell.count() < quantity:
                context['error'] = f"Only {assets_to_sell.count()} units of {asset_type_obj.name} are available. Sale cancelled."
                return render(request, 'inventory/bulk_sale_form.html', context)

            with transaction.atomic():
                for asset in assets_to_sell:
                    
                    asset.status = 'SOLD'
                    asset.save() 
                    
                    cost_basis = asset.purchase_price 
                    profit_loss = sale_price_per_unit - cost_basis # DECIMAL CALCULATION
                    
                    AssetRetirementSale.objects.create(
                        asset=asset,
                        sale_price=sale_price_per_unit,
                        cost_basis=cost_basis,
                        profit_loss=profit_loss
                    )
            
            messages.success(request, f"Successfully sold {quantity} units of {asset_type_obj.name}.")
            return redirect('asset_list')
            
        except AssetType.DoesNotExist:
            context['error'] = "Invalid Asset Type selected."
            return render(request, 'inventory/bulk_sale_form.html', context)
        except Exception as e:
            context['error'] = f"An unexpected error occurred: {e}"
            return render(request, 'inventory/bulk_sale_form.html', context)


# --- 7. START MIXED SALE VIEW (Asset Selection) ---
@login_required
def start_mixed_sale_view(request):
    
    context = get_base_context()
    
    # 1. Base Query: Assets available to sell
    assets_to_select = HardwareAsset.objects.filter(
        status__in=['IN_STOCK', 'PENDING_SALE']
    ).select_related('asset_type').order_by('asset_type__name', 'model_number')
    
    # 2. PAGINATION LOGIC (New)
    page_number = request.GET.get('page')
    paginator = Paginator(assets_to_select, 30) # Use 25 items per page
    
    try:
        page_obj = paginator.get_page(page_number)
    except Exception:
        # Handle cases where page number is invalid, defaulting to page 1
        page_obj = paginator.get_page(1)
    
    context.update({
        # Use the paginated object in the context
        'assets': page_obj, 
        'num_items': assets_to_select.count(), # Total count
    })
    
    if request.method == 'POST':
        # ... (POST logic for handling selections remains the same) ...
        # Get selected asset IDs from the current page
        selected_asset_ids = request.POST.getlist('selected_assets') 
        
        # Merge with existing IDs in session (if any)
        current_selection = request.session.get('mixed_sale_assets', [])
        
        # Add new selections, converting the IDs back to strings if necessary
        new_selection = list(set(current_selection + selected_asset_ids)) 
        
        if not new_selection:
            messages.error(request, "Please select at least one asset to sell.")
            # Use the correct template name for the selection view
            return render(request, 'inventory/mixed_sale_select.html', context)

        request.session['mixed_sale_assets'] = new_selection
        
        return redirect('finalize_mixed_sale')

    # GET request render
    return render(request, 'inventory/mixed_sale_select.html', context)

# --- 8. FINALIZE MIXED SALE VIEW (Checkout) ---
@login_required
@require_http_methods(["GET", "POST"])
def finalize_mixed_sale_view(request):
    
    context = get_base_context()
    selected_asset_ids = request.session.get('mixed_sale_assets', [])
    
    if not selected_asset_ids:
        messages.error(request, "No assets selected for sale. Please start a new selection.")
        return redirect('start_mixed_sale')

    # Fetch assets for sale
    assets_to_sell = HardwareAsset.objects.filter(pk__in=selected_asset_ids).select_related('asset_type')
    
    total_cost_basis = sum(asset.purchase_price for asset in assets_to_sell)
    
    context.update({
        'assets': assets_to_sell,
        'total_cost_basis': total_cost_basis,
        'num_items': assets_to_sell.count(),
        
        # CRITICAL FIX: Initialize sale_data as an empty dictionary 
        # for GET requests to prevent the AttributeError in the template filter.
        'sale_data': {}, 
    })
    
    if request.method == 'POST':
        
        try:
            sale_data = {}
            total_sale_price_sum = Decimal('0.00')
            
            # 1. RETRIEVE AND VALIDATE ALL INPUTS
            total_discount_str = request.POST.get('total_discount', '0.00').strip()
            total_discount = Decimal(total_discount_str)
            
            if total_discount < 0:
                 raise ValueError("Discount cannot be negative.")

            # Retrieve and validate prices for EACH item
            for asset in assets_to_sell:
                price_key = f'sale_price_{asset.pk}'
                price_str = request.POST.get(price_key, '').strip() 
                
                if not price_str:
                    raise ValueError(f"Sale Price missing for item S/N: {asset.serial_number}")

                item_sale_price = Decimal(price_str)
                sale_data[asset.pk] = item_sale_price
                total_sale_price_sum += item_sale_price
            
            if total_sale_price_sum <= total_discount:
                 raise ValueError("Total discount must be less than the total sale price.")
            
            
            # 2. APPLY PROPORTIONAL DISCOUNT (If any)
            final_sale_data = {}
            total_remaining_discount = total_discount
            
            # Apply discount proportionally based on each item's price
            if total_discount > Decimal('0.00'):
                
                for i, asset in enumerate(assets_to_sell):
                    item_sale_price = sale_data[asset.pk]
                    
                    if i < len(assets_to_sell) - 1:
                        # Calculate proportional discount for this item
                        proportion = item_sale_price / total_sale_price_sum
                        discount_amount = proportion * total_discount
                        
                        # Round and adjust for the next item
                        # Use ROUND_HALF_UP or similar if strict rounding rules are needed
                        discount_amount = discount_amount.quantize(Decimal('0.01')) 
                        
                        final_sale_price = item_sale_price - discount_amount
                        final_sale_data[asset.pk] = final_sale_price
                        total_remaining_discount -= discount_amount
                    else:
                        # Last item takes the remaining unallocated discount to ensure total discount is exact
                        final_sale_data[asset.pk] = item_sale_price - total_remaining_discount
                        
            else:
                final_sale_data = sale_data # No discount, use original prices
            
            
            # 3. Finalize the transaction
            with transaction.atomic():
                for asset in assets_to_sell:
                    sale_price = final_sale_data.get(asset.pk)
                    
                    # Update Asset Status
                    asset.status = 'SOLD'
                    asset.pending_sale_price = None 
                    asset.save()
                    
                    # Create Sale Record
                    cost_basis = asset.purchase_price
                    profit_loss = sale_price - cost_basis 
                    
                    AssetRetirementSale.objects.create(
                        asset=asset,
                        sale_price=sale_price,
                        cost_basis=cost_basis,
                        profit_loss=profit_loss
                    )
            
            # 4. Clear session and redirect
            del request.session['mixed_sale_assets']
            messages.success(request, f"Successfully finalized sale for {assets_to_sell.count()} assets. Total Discount Applied: ${total_discount_str}")
            return redirect('asset_list')

        except ValueError as e:
            messages.error(request, f"Failed to finalize sale. Input error: {e}")
            # Ensure the current data is preserved for re-rendering
            context['sale_data'] = request.POST 
            return render(request, 'inventory/mixed_sale_finalize.html', context)
        
        except Exception as e:
            messages.error(request, f"An unexpected error occurred during sale finalization: {e}")
            return render(request, 'inventory/mixed_sale_finalize.html', context)
            
    # GET request render
    return render(request, 'inventory/mixed_sale_finalize.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def remove_from_mixed_sale(request, asset_pk):
    """Removes a single asset by its primary key from the mixed sale cart in the session."""
    
    asset_pk_str = str(asset_pk)
    
    if 'mixed_sale_cart' in request.session:
        # Get cart or default to empty list
        cart_list = request.session.get('mixed_sale_cart', [])
        
        try:
            cart_list.remove(asset_pk_str)
            # Must explicitly set the session value to tell Django it has been modified
            request.session['mixed_sale_cart'] = cart_list
            messages.info(request, f"Asset ID #{asset_pk} removed from cart.")
            
        except ValueError:
            messages.error(request, f"Asset ID #{asset_pk} was not found in the cart.")
            
    # Redirect back to the cart building page (start_mixed_sale)
    return redirect('start_mixed_sale') 
@login_required
@require_http_methods(["GET", "POST"])
def add_to_mixed_sale_from_list(request, asset_pk):
    """Adds a single available asset to the mixed sale cart from the full inventory list."""
    
    # Check if the asset exists and is in stock
    asset = get_object_or_404(HardwareAsset, pk=asset_pk)
    
    if asset.status != 'IN_STOCK':
        messages.error(request, f"Asset {asset.serial_number} is not In Stock and cannot be added.")
    else:
        asset_pk_str = str(asset_pk)
        
        # Get cart or initialize as empty list if it doesn't exist
        cart_list = request.session.get('mixed_sale_cart', [])
        
        if asset_pk_str not in cart_list:
            cart_list.append(asset_pk_str)
            request.session['mixed_sale_cart'] = cart_list
            messages.success(request, f"Asset {asset.serial_number} added to cart.")
        else:
            messages.warning(request, f"Asset {asset.serial_number} is already in the cart.")

    # Redirect back to the cart building page (start_mixed_sale)
    return redirect('start_mixed_sale')

