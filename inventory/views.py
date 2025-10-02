# inventory/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.contrib import messages 
from django.core.paginator import Paginator
from decimal import Decimal
import datetime
from .forms import AssetForm  # <--- FIX: Import the AssetForm
from .forms import AssetForm # ... maybe other forms too
from .forms import AssetForm, BulkSaleForm  # <-- This line MUST include BulkSaleForm

# Import all models (Ensure these paths are correct)
from .models import HardwareAsset, AssetType, AssetRetirementSale, MaintenanceLog 
# from .forms import HardwareAssetForm # Uncomment if you have forms

# --- BASE CONTEXT HELPER ---
def get_base_context(): 
    """Returns the base context including branding variables."""
    # NOTE: You should ensure 'nuclear-logo.png' is in your STATICFILES_DIRS 
    # and accessible via the static tag, or use the path provided in your image 
    # (e.g., 'Company_Logos/nuclear-logo-circle-shape-yellow-260nw-2650265353.webp')
    return {
        'SHOP_NAME': 'Nuclear General Hardware', 
        'SHOP_LOGO_URL': 'nuclear-logo.png', 
    }

# --- 1. ASSET LIST VIEW (Fixed for filters and pagination) ---
@login_required 
def asset_list_view(request): 
    # --- 1. INITIALIZE FILTER VARIABLES ---
    status_filter = request.GET.get('status')
    location_filter = request.GET.get('location')
    asset_type_filter = request.GET.get('asset_type') 
    
    # --- 2. BASE QUERY AND FILTERING ---
    assets = HardwareAsset.objects.all().select_related('asset_type').prefetch_related('sale_record').order_by('id') 

    if status_filter:
        assets = assets.filter(status=status_filter)
    if location_filter:
        assets = assets.filter(location=location_filter)
    if asset_type_filter:
        # Filter by primary key (ID) of AssetType
        assets = assets.filter(asset_type__pk=asset_type_filter)
        
    # --- 3. PAGINATION LOGIC ---
    page_number = request.GET.get('page')
    paginator = Paginator(assets, 30) 
    
    try:
        page_obj = paginator.get_page(page_number) 
    except Exception as e:
        page_obj = paginator.get_page(1)
        
    # --- 4. CONTEXT ASSEMBLY ---
    context = get_base_context() 
    all_asset_types = AssetType.objects.all().order_by('name') 
    
    context.update({
        'assets': page_obj, 
        'ALL_ASSET_TYPES': all_asset_types, 
        'STATUS_CHOICES': HardwareAsset.STATUS_CHOICES,
        'LOCATIONS': HardwareAsset.LOCATION_CHOICES,
        'current_status': status_filter, 
        'current_location': location_filter, 
        'current_asset_type': asset_type_filter, 
    })

    return render(request, 'inventory/asset_list.html', context)


# --- 2. DUMMY/PLACEHOLDER VIEWS (For completeness) ---
@login_required 
def add_asset_view(request):
    # Get necessary data for select fields in both GET and POST
    asset_types = AssetType.objects.all().order_by('name')
    locations = HardwareAsset.LOCATION_CHOICES # This remains correct

    if request.method == 'POST':
        # Use a form object to handle core fields and validation
        form = AssetForm(request.POST) 
        
        # Manually extract the custom fields not in the AssetForm Meta
        quantity = int(request.POST.get('quantity', 1))
        custom_serial = request.POST.get('serial_number', '').strip()

        if form.is_valid():
            # The logic for bulk saving goes here (Simplified for this example)
            
            # 1. Get the base data from the valid form
            cleaned_data = form.cleaned_data
            
            # 2. Check for single item/custom serial number constraint
            if quantity == 1 and custom_serial and HardwareAsset.objects.filter(serial_number=custom_serial).exists():
                 messages.error(request, f"Error: Serial number '{custom_serial}' already exists.")
                 form = AssetForm(request.POST) # Re-render form with data
            else:
                # --- BULK/SINGLE ASSET CREATION LOGIC ---
                
                # 1. Get the AssetType object
                asset_type_pk = cleaned_data['asset_type'].pk
                try:
                    asset_type_obj = AssetType.objects.get(pk=asset_type_pk)
                except AssetType.DoesNotExist:
                    messages.error(request, "Invalid Asset Type selected.")
                    return redirect('add_asset') 
                
                created_count = 0
                
                try:
                    # Use a transaction for safety: all or nothing
                    with transaction.atomic():
                        
                        for i in range(quantity):
                            # Determine the serial number:
                            # 1. For quantity=1, use the custom serial for the first item (if provided)
                            # 2. Otherwise, auto-generate for every item
                            is_custom = (quantity == 1 and i == 0 and custom_serial)
                            
                            serial_num = get_next_serial_number(
                                asset_type_obj, 
                                custom_serial if is_custom else None
                            )

                            # Create the new asset record
                            HardwareAsset.objects.create(
                                asset_type=asset_type_obj,
                                model_number=cleaned_data['model_number'],
                                purchase_price=cleaned_data['purchase_price'],
                                location=cleaned_data['location'],
                                warranty_end_date=cleaned_data['warranty_end_date'],
                                serial_number=serial_num,
                                status='IN_STOCK' # Default status for newly added assets
                            )
                            created_count += 1
                        
                    messages.success(request, f"Successfully created {created_count} asset record(s)!")
                    return redirect('asset_list') 

                except Exception as e:
                    messages.error(request, f"An unexpected error occurred during asset creation: {e}")
                    # Fall through to re-render form with errors
        else:
            messages.error(request, "Error adding asset. Please check the required fields.")
            form = AssetForm(request.POST) # Re-render form with data

    else: # GET request
        form = AssetForm()

    context = {
        'form': form, # Pass the form object
        'asset_types': asset_types, # Now contains a QuerySet of AssetType objects
        'LOCATIONS': locations,     # Used for non-form rendering/debugging if needed
        'SHOP_NAME': 'Nuclear General Hardware', 
        # Ensure the logo URL is correct based on your base.html fix:
        'SHOP_LOGO_URL': '/static/Company_Logos/nuclear-logo-circle-shape-yellow-260nw-2650265353.webp'
    }
    
    return render(request, 'inventory/add_asset_form.html', context)
@login_required 
def asset_detail_view(request, pk):
    asset = get_object_or_404(HardwareAsset, pk=pk)
    context = {**get_base_context(), 'asset': asset}
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
def bulk_sale_view(request):
    messages.info(request, "Placeholder: Bulk Sale View")
    return redirect('asset_list')

@login_required
def add_to_mixed_sale_from_list(request, asset_pk):
    mixed_sale_assets = request.session.get('mixed_sale_assets', [])
    asset_pk_str = str(asset_pk)
    if asset_pk_str not in mixed_sale_assets:
        mixed_sale_assets.append(asset_pk_str)
        request.session['mixed_sale_assets'] = mixed_sale_assets
        request.session.modified = True
        messages.success(request, f"Asset ID {asset_pk} added to the mixed sale cart.")
    return redirect('asset_list')


# --- 3. MIXED SALE WORKFLOW VIEWS ---

# --- 3.1. START MIXED SALE VIEW (Asset Selection) ---
@login_required
def start_mixed_sale_view(request):
    context = get_base_context()

    # 1. Handle form submission (POST) - Adding selected items to session
    if request.method == 'POST':
        mixed_sale_assets = request.session.get('mixed_sale_assets', [])
        selected_assets = request.POST.getlist('selected_assets')
        
        newly_added_count = 0
        for asset_pk in selected_assets:
            if asset_pk not in mixed_sale_assets:
                mixed_sale_assets.append(asset_pk)
                newly_added_count += 1
        
        request.session['mixed_sale_assets'] = mixed_sale_assets
        request.session.modified = True 
        
        if newly_added_count > 0:
            messages.success(request, f"{newly_added_count} asset(s) added to the mixed sale cart. Total items: {len(mixed_sale_assets)}")
        elif not selected_assets:
            messages.warning(request, "No new assets were selected to add to the cart.")
            
        # Preserve page number upon redirect
        return redirect(request.path + '?' + request.META['QUERY_STRING'])


    # 2. Handle page display (GET)
    assets = HardwareAsset.objects.filter(status='IN_STOCK').order_by('pk')
    
    paginator = Paginator(assets, 30) 
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        **get_base_context(),
        'assets': page_obj,
        'num_items': assets.count(),
    }
    
    return render(request, 'inventory/mixed_sale_select.html', context)


# --- 3.2. FINALIZE MIXED SALE VIEW (Checkout/Processing) ---
@login_required
@require_http_methods(["GET", "POST"])
def finalize_mixed_sale_view(request):
    
    context = get_base_context()
    selected_asset_ids = request.session.get('mixed_sale_assets', [])
    
    if not selected_asset_ids:
        # Redirect to the main list if the cart is empty
        messages.error(request, "No assets selected for sale. Please start a new selection.")
        return redirect('asset_list') 

    # Fetch assets for sale, ordered by PK for deterministic discount application
    assets_to_sell = HardwareAsset.objects.filter(pk__in=selected_asset_ids).select_related('asset_type').order_by('pk')
    
    total_cost_basis = sum(asset.purchase_price for asset in assets_to_sell)
    
    context.update({
        'assets': assets_to_sell,
        'total_cost_basis': total_cost_basis,
        'num_items': assets_to_sell.count(),
        'sale_data': request.POST if request.method == 'POST' else {}, # Preserve form data on error
    })
    
    if request.method == 'POST':
        try:
            sale_data = {} # To store un-discounted item prices
            total_sale_price_sum = Decimal('0.00')
            
            # --- 1. RETRIEVE AND VALIDATE ALL INPUTS ---
            total_discount_str = request.POST.get('total_discount', '0.00').strip()
            # Ensure Decimal precision context
            total_discount = Decimal(total_discount_str).quantize(Decimal('0.01'))
            
            if total_discount < 0:
                 raise ValueError("Discount cannot be negative.")

            # Retrieve and validate prices for EACH item
            for asset in assets_to_sell:
                price_key = f'sale_price_{asset.pk}'
                price_str = request.POST.get(price_key, '').strip() 
                
                if not price_str:
                    raise ValueError(f"Sale Price missing for item S/N: {asset.serial_number}")

                item_sale_price = Decimal(price_str).quantize(Decimal('0.01'))
                
                if item_sale_price <= 0:
                    raise ValueError(f"Sale price must be positive for item S/N: {asset.serial_number}")
                    
                sale_data[asset.pk] = item_sale_price
                total_sale_price_sum += item_sale_price
            
            if total_sale_price_sum <= total_discount and total_sale_price_sum > Decimal('0.00'):
                 raise ValueError("Total discount must be less than the total gross sale price.")
            
            
            # --- 2. APPLY PROPORTIONAL DISCOUNT ---
            final_sale_data = {}
            total_remaining_discount = total_discount
            
            if total_discount > Decimal('0.00'):
                for i, asset in enumerate(assets_to_sell):
                    item_sale_price = sale_data[asset.pk]
                    
                    if i < len(assets_to_sell) - 1:
                        # Calculate proportional discount amount
                        proportion = item_sale_price / total_sale_price_sum
                        discount_amount = (proportion * total_discount).quantize(Decimal('0.01'))
                        
                        final_sale_price = item_sale_price - discount_amount
                        final_sale_data[asset.pk] = final_sale_price
                        total_remaining_discount -= discount_amount
                    else:
                        # Last item takes the remainder of the discount to ensure the total is exact
                        final_sale_data[asset.pk] = item_sale_price - total_remaining_discount
            else:
                final_sale_data = sale_data # No discount applied

            
            # --- 3. Finalize the transaction and update database ---
            with transaction.atomic():
                total_sold = 0
                for asset in assets_to_sell:
                    sale_price = final_sale_data.get(asset.pk)
                    
                    # 3.1. Update Asset Status
                    asset.status = 'SOLD'
                    asset.pending_sale_price = None 
                    asset.save()
                    
                    # 3.2. Create Sale Record (The model's save() method calculates P/L)
                    AssetRetirementSale.objects.create(
                        asset=asset,
                        # Pass the final, discounted sale price
                        sale_price=sale_price, 
                        # cost_basis and profit_loss are calculated in AssetRetirementSale.save()
                    )
                    total_sold += 1
            
            # --- 4. Clear session and redirect ---
            del request.session['mixed_sale_assets']
            messages.success(request, f"Successfully finalized sale for {total_sold} assets. Total Discount Applied: ${total_discount:,.2f}")
            return redirect('asset_list')

        except (ValueError, TypeError) as e:
            messages.error(request, f"Failed to finalize sale. Input error: {e}")
            return render(request, 'inventory/mixed_sale_finalize.html', context)
        
        except Exception as e:
            # Catch database or unexpected errors
            messages.error(request, f"An unexpected error occurred during sale finalization: {e}")
            return render(request, 'inventory/mixed_sale_finalize.html', context)
            
    # GET request render
    return render(request, 'inventory/mixed_sale_finalize.html', context)


@login_required
@require_http_methods(["GET", "POST"]) # Ensure POST is allowed if using a link that might be seen as GET
def remove_from_mixed_sale_view(request, asset_pk):

    """Removes a single asset from the mixed sale session cart."""
    # Ensure asset_pk (from URL) is treated as a string, matching how it's stored
    asset_pk_str = str(asset_pk) 
    
    # Retrieve the cart, making sure it defaults safely to an empty list
    cart = request.session.get('mixed_sale_assets', [])
    
    # --- Convert all cart items to strings for robust comparison ---
    # This prevents errors if an integer somehow crept into the session list
    cart_as_strings = [str(item) for item in cart]
    
    # Now check and remove from the string-safe list
    if asset_pk_str in cart_as_strings:
        cart_as_strings.remove(asset_pk_str)
        
        # Save the updated list back to the session
        request.session['mixed_sale_assets'] = cart_as_strings
        request.session.modified = True 
        
        messages.success(request, f"Asset ID {asset_pk} was successfully removed from the mixed sale cart.")
        
    else:
        messages.warning(request, f"Asset ID {asset_pk} was not found in the mixed sale cart.")

    # Redirect the user back to the finalize view or the list where they clicked remove
    return redirect('finalize_mixed_sale') 

def get_next_serial_number(asset_type_obj, custom_serial=None):
    """
    Generates the next serial number based on the asset type's name 
    (used to create a 3-letter prefix), or returns the custom serial if provided.
    """
    # Use the custom serial if provided (for quantity=1)
    if custom_serial:
        return custom_serial
        
    # --- FIX: Generate prefix from the object's name ---
    # Example: 'Cement' becomes 'CEM'
    # Use the first 3 characters of the name, converted to uppercase.
    # We use a slice [:3] to safely handle names shorter than 3 characters too.
    prefix = asset_type_obj.name[:3].upper()
    # ----------------------------------------------------
    
    # We assume the generated serial numbers will look like 'CEM-000001'
    
    # 1. Look up the highest existing serial number for this prefix
    try:
        last_asset = HardwareAsset.objects.filter(
            serial_number__startswith=f'{prefix}-'
        ).latest('serial_number') 
        
        # Example: BRU-000033. We want '000033'
        last_number_str = last_asset.serial_number.split('-')[-1]
        
        # Convert to int, increment, and handle potential errors
        last_number = int(last_number_str)
        next_number = last_number + 1
        
    except HardwareAsset.DoesNotExist:
        # If no assets of this type exist yet, start at 1
        next_number = 1
        
    # Format the number part (e.g., 1 becomes 000001, assuming 6 digits)
    return f"{prefix}-{next_number:06d}"

@login_required
def bulk_sale_view(request):
    
    if request.method == 'POST':
        form = BulkSaleForm(request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            asset_type = cleaned_data['asset_type']
            quantity = cleaned_data['quantity']
            unit_sale_price = cleaned_data['unit_sale_price']
            
            # --- VALIDATION: Check for enough stock ---
            available_assets = HardwareAsset.objects.filter(
                asset_type=asset_type, 
                status='IN_STOCK'
            ).order_by('pk') # Order by PK to sell the oldest ones first
            
            if available_assets.count() < quantity:
                messages.error(request, f"Error: Only {available_assets.count()} {asset_type.name}(s) are currently IN_STOCK. Cannot sell {quantity}.")
                # Fall through to re-render the form with error message
            else:
                # --- CORE TRANSACTION LOGIC ---
                try:
                    with transaction.atomic():
                        # 1. Select the assets to be sold (the first 'quantity' in stock)
                        assets_to_sell = list(available_assets[:quantity])
                        
                        # 2. Update their status and create sale records
                        for asset in assets_to_sell:
                            # Update Asset Status
                            asset.status = 'SOLD'
                            asset.save()
                            
                            # Create Sale Record (This model's save() method should calculate P/L)
                            AssetRetirementSale.objects.create(
                                asset=asset,
                                sale_price=unit_sale_price, # Use the per-unit price
                            )
                            
                    messages.success(request, f"Successfully sold {quantity} unit(s) of {asset_type.name} at ${unit_sale_price} per unit.")
                    return redirect('asset_list')
                
                except Exception as e:
                    messages.error(request, f"A database error occurred during bulk sale: {e}")
        
    else: # GET request
        form = BulkSaleForm()
        
    context['form'] = form
    return render(request, 'inventory/bulk_sale_form.html', context)