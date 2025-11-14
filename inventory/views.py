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
from decimal import Decimal, InvalidOperation
import datetime
from django.http import JsonResponse
import json 
from django.contrib.messages.views import SuccessMessageMixin
from django.utils import timezone # ⬅️ ADD THIS
from .models import HardwareAsset as Asset, AssetType, SaleRecord, MaintenanceLog, MixedSale
from .forms import AssetForm, BulkSaleForm, AssetFilterForm, MaintenanceLogForm # Ensure this line imports BulkSaleForm
from collections import defaultdict
from django.db.models.functions import TruncDate, Coalesce
import logging
import csv
from django.http import HttpResponse # <-- Needed for export
from django.db.models import Sum, Count, F, Q, Case, When, Value, CharField, DateField
logger = logging.getLogger(__name__)
# --- BASE CONTEXT HELPER (MODIFIED to accept request) ---
@login_required
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
@login_required
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
CART_KEY = 'mixed_sale_cart'
@login_required
@require_http_methods(["POST"]) 
def add_to_mixed_sale(request):
    
    # 1. Decode the JSON body
    try:
        data = json.loads(request.body)
        asset_pk_str = str(data.get('asset_pk'))
        
        if not asset_pk_str or asset_pk_str == 'None':
             return JsonResponse({'success': False, 'message': 'Missing asset_pk.'}, status=400)
             
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON format.'}, status=400)
    except KeyError:
        return JsonResponse({'success': False, 'message': 'Missing required key asset_pk.'}, status=400)
        
    # 2. Retrieve the current cart and check asset availability
    # FIX: Using the standardized CART_KEY
    cart = request.session.get(CART_KEY, [])
    
    try:
        # Check if asset exists and is in stock
        Asset.objects.get(pk=asset_pk_str, status='IN_STOCK')
        
        if asset_pk_str not in cart:
            # 3. Add to cart (session)
            cart.append(asset_pk_str)
            
            # FIX: Saving to the standardized CART_KEY
            request.session[CART_KEY] = cart
            request.session.modified = True
            
            return JsonResponse({
                'success': True,
                'mixed_sale_count': len(cart),
                'message': f"Asset {asset_pk_str} added to cart."
            })
        else:
            # 4. Asset already in cart
            return JsonResponse({
                'success': True, 
                'mixed_sale_count': len(cart),
                'message': f"Asset {asset_pk_str} is already in the cart."
            })
            
    except Asset.DoesNotExist:
        # 5. Asset not found or not in stock
        return JsonResponse({
            'success': False,
            'mixed_sale_count': len(cart),
            'message': f"Error: Asset {asset_pk_str} not found or is currently unavailable."
        }, status=404)
@login_required
def bulk_sale_view(request):
    # Initialize form for GET/rendering
    form = BulkSaleForm()
    assets_to_sell = [] 

    if request.method == 'POST':
        form = BulkSaleForm(request.POST)
        
        if form.is_valid():
            asset_type = form.cleaned_data['asset_type']
            quantity = form.cleaned_data['quantity']
            price_per_unit = form.cleaned_data['unit_sale_price']
            
            # 🎯 NEW: Get the location from the form
            location = form.cleaned_data['location']
            
            # Ensure price is a Decimal for precise calculations
            try:
                # Cast the price to Decimal using the imported Decimal class
                price_per_unit_decimal = Decimal(price_per_unit)
            except Exception:
                messages.error(request, "Invalid price per unit.")
                return redirect('bulk_sale')

            total_sale_amount = price_per_unit_decimal * Decimal(quantity)
            
            # 1. Get the assets to sell, NOW FILTERED BY LOCATION
            # Use select_for_update to lock assets during transaction
            assets_to_sell = Asset.objects.filter(
                asset_type=asset_type,
                status='IN_STOCK',
                location=location # <-- CRITICAL FILTER ADDED HERE
            ).order_by('purchase_date').select_for_update()[:quantity] # Lock selected assets
            
            if len(assets_to_sell) < quantity:
                messages.error(request, f"Not enough assets in stock at {location} for {asset_type.name}. Requested: {quantity}, Available: {len(assets_to_sell)}")
                return redirect('bulk_sale')

            try:
                # Use a transaction to ensure all updates succeed or fail together
                with transaction.atomic():
                    # 2. Create the SaleRecord object
                    # NOTE: Assuming SaleRecord has a location field. If not, you must add it.
                    sale_record = SaleRecord.objects.create(
                        total_sale_price=total_sale_amount, 
                        sale_type='BULK',
                        # Optionally add the location to the SaleRecord itself
                        # location=location 
                    )

                    # 3. Update the individual Assets
                    for asset in assets_to_sell:
                        asset.status = 'SOLD'
                        asset.sale_record = sale_record
                        asset.individual_sale_price = price_per_unit_decimal
                        # No need to update asset.location as the filter ensured it was correct
                        asset.save()
                        
                # 4. CRITICAL: REDIRECT AFTER SUCCESSFUL TRANSACTION
                messages.success(request, f"Successfully marked {quantity} units of {asset_type.name} from {location} as SOLD for a total of ${total_sale_amount:,.2f}.")
                return redirect('asset_list')
                
            except Exception as e:
                messages.error(request, f"A database error occurred during sale finalization: {e}")
                # Optional: Log the exception to server logs
                return redirect('bulk_sale')

    # --- GET Request or Invalid POST Form ---
    context = {
        'form': form,
        'assets_to_sell': assets_to_sell, 
    }
    
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
    CART_KEY = 'mixed_sale_cart'
    # 1. FETCH ASSET IDs (Used for both GET and POST)
    cart_asset_pks = request.session.get(CART_KEY, [])
    
    # Check if cart is empty and redirect if necessary
    if not cart_asset_pks:
        messages.warning(request, "The mixed sale cart is empty.")
        return redirect('asset_list') 
    
    # Fetch assets once for both POST and GET logic
    assets_to_sell = Asset.objects.filter(pk__in=cart_asset_pks)
    
    # 2. POST REQUEST HANDLING (Form Submission)
    if request.method == 'POST':
        
        total_sale_price = Decimal('0.00')
        sale_data = {}
        validation_error = False
        
        # Process the posted individual sale prices
        for asset in assets_to_sell:
            input_name = f'sale_price_{asset.pk}'
            sale_price_str = request.POST.get(input_name, '0.00')
            
            try:
                sale_price = Decimal(sale_price_str)
                profit_loss = sale_price - asset.purchase_price
                
                sale_data[asset.pk] = {
                    'sale_price': sale_price,
                    'profit_loss': profit_loss,
                }
                
                total_sale_price += sale_price
                
            except InvalidOperation:
                messages.error(request, f"Invalid price entered for Asset ID {asset.pk}. Please use a valid number.")
                validation_error = True
                break # Exit the loop immediately on error

        # If there were validation errors, fall through to the GET context rendering
        if validation_error:
            # Code falls to the rendering block at the bottom
            pass
        
        # If no validation errors, proceed with saving the transaction
        else: 
            # 3. Create and Save Records
            with transaction.atomic():
                total_purchase_cost = sum(asset.purchase_price for asset in assets_to_sell)

                mixed_sale = MixedSale.objects.create(
                    total_sale_price=total_sale_price,
                    total_purchase_cost=total_purchase_cost,
                    sale_date=timezone.now(),
                    # user=request.user, # Recommended
                )
                
                # 4. Update EACH Asset
            for asset in assets_to_sell:
                data = sale_data[asset.pk]
                
                # FIX: Assign the MixedSale instance to the NEW 'mixed_sale' field
                asset.mixed_sale = mixed_sale 

                asset.individual_sale_price = data['sale_price']
                #asset.profit_loss = data['profit_loss']
                asset.status = 'SOLD'
                
                asset.save()
                    
            # 5. Clear the cart and REDIRECT after successful save
            request.session.pop(CART_KEY, None)
            messages.success(request, f"Sale of {len(assets_to_sell)} items finalized successfully!")
            return redirect('asset_list') # Final successful exit

    # 6. GET REQUEST/FALLBACK HANDLING (Render the Page)
    # This code runs on a GET request, or if the POST request hits a validation error.
    
    # Group assets for template display (using the previously fetched assets_to_sell)
    grouped_assets = defaultdict(list)
    total_purchase_cost = Decimal('0.00')
    
    for asset in assets_to_sell:
        type_name = asset.asset_type.name if asset.asset_type else 'NO TYPE ASSIGNED'
        location_name = asset.get_location_display() or 'UNKNOWN LOCATION'
        grouped_assets[(type_name, location_name)].append(asset)
        total_purchase_cost += asset.purchase_price
    
    logger.warning(f"Grouped Assets: {grouped_assets.items()}")
    
    context = {
        'assets_to_sell': assets_to_sell,
        'grouped_assets_list': list(grouped_assets.items()), 
        'total_purchase_cost': total_purchase_cost,
    }
    return render(request, 'inventory/mixed_sale_finalize.html', context)
@login_required
@require_http_methods(["POST"]) 
def remove_from_mixed_sale(request):
    """
    Removes an asset from the session-based mixed sale cart via an AJAX POST request.
    """
    
    # 1. Decode the JSON body
    try:
        data = json.loads(request.body)
        asset_pk_str = str(data.get('asset_pk'))
        
        if not asset_pk_str or asset_pk_str == 'None':
             return JsonResponse({'success': False, 'message': 'Missing asset_pk.'}, status=400)
             
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'success': False, 'message': 'Invalid data format or missing asset_pk.'}, status=400)
        
    # 2. Get the current cart from the session
    cart = request.session.get('mixed_sale_assets', [])
    
    # 3. Perform removal
    if asset_pk_str in cart:
        cart.remove(asset_pk_str)
        request.session['mixed_sale_assets'] = cart
        request.session.modified = True
        
        return JsonResponse({
            'success': True,
            'mixed_sale_count': len(cart),
            'message': f"Asset {asset_pk_str} removed from cart."
        })
    else:
        # Item was already missing, still return success to update button state
        return JsonResponse({
            'success': True,
            'mixed_sale_count': len(cart),
            'message': f"Asset {asset_pk_str} was not found in the cart (no change made)."
        })

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

@login_required
def sales_dashboard_view(request):
    # Base Query: Filter for all assets marked as SOLD
    # NOTE: Assuming 'Asset' in your original snippet is 'HardwareAsset'
    sold_assets = Asset.objects.filter(status='SOLD') 
    
    # --- 1. Total Sales Metrics (Calculated from individual assets) ---
    total_metrics = sold_assets.aggregate(
        total_revenue=Sum('individual_sale_price'),
        # CRITICAL FIX: Calculate the sum of (Sale Price - Purchase Price)
        net_profit=Sum(F('individual_sale_price') - F('purchase_price')),
        total_sales_count=Count('pk') # Total number of items sold
    )
    
    # Calculate Total Transactions: Sum of unique SaleRecord IDs and unique MixedSale IDs
    transaction_count = SaleRecord.objects.all().count() + MixedSale.objects.all().count()
    
    # Clean up None values
    total_metrics['total_revenue'] = total_metrics['total_revenue'] or 0
    total_metrics['net_profit'] = total_metrics['net_profit'] or 0
    total_metrics['total_sales_count'] = sold_assets.count()
    total_metrics['total_transactions'] = transaction_count 

    # --- 2. Sales by Type (Bulk vs. Mixed) ---
    # Annotate each asset with its sale type (Mixed or Bulk)
    sales_by_type_annotated = sold_assets.annotate(
        # Use Case/When to assign a clear label based on which FK is NOT NULL
        sale_type_label=Case(
            When(sale_record__isnull=False, then=Value('BULK')),
            When(mixed_sale__isnull=False, then=Value('MIXED')),
            default=Value('UNKNOWN'), # Catch unassigned sold assets
            output_field=CharField()
        )
    )
    
    # Group by the new annotated field
    sales_by_type_grouped = sales_by_type_annotated.values('sale_type_label').annotate(
        revenue=Sum('individual_sale_price'),
        profit=Sum(F('individual_sale_price') - F('purchase_price')),
        assets_sold=Count('pk')
    ).order_by('sale_type_label')

    # Add transaction count back in 
    bulk_txns = SaleRecord.objects.all().count()
    mixed_txns = MixedSale.objects.all().count()

    final_sales_by_type = []
    for entry in sales_by_type_grouped:
        if entry['sale_type_label'] == 'BULK':
            entry['transaction_count'] = bulk_txns
        elif entry['sale_type_label'] == 'MIXED':
            entry['transaction_count'] = mixed_txns
        else:
             entry['transaction_count'] = 0 # Handle UNKNOWN sales
        
        final_sales_by_type.append(entry)


    # --- 3. Sales Trend by Date (FIXED GROUPING BY DAY) ---
    
    sales_by_date = sold_assets.annotate(
        # Use Coalesce to pick the date from MixedSale or SaleRecord
        sale_date=Coalesce(
            F('mixed_sale__sale_date'), 
            F('sale_record__sale_date'),
            output_field=DateField() # Coalesce returns a DateField
        )
    ).filter(sale_date__isnull=False).annotate(
        # Use TruncDate on the Coalesced date field for grouping by day
        date_group=TruncDate('sale_date') 
    ).values('date_group').annotate(
        daily_revenue=Sum('individual_sale_price'),
        daily_profit=Sum(F('individual_sale_price') - F('purchase_price')),
        daily_assets_sold=Count('pk') # This counts assets sold per day
    ).order_by('-date_group')

    context = get_base_context(request)
    context.update({
        'total_metrics': total_metrics,
        'sales_by_type': final_sales_by_type,
        'sales_by_date': sales_by_date,
    })
    
    return render(request, 'inventory/sales_dashboard.html', context)


# ----------------------------------------------------
# B. Export Sales Data View 
# --------------------------------------------
@login_required
def export_sales_data_view(request):
    """
    Exports sales data (HardwareAsset records) to a CSV file.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_export.csv"'

    writer = csv.writer(response)
    
    writer.writerow([
        'Asset ID', 
        'Type', 
        'Model', 
        'Serial Number', 
        'Status', 
        'Purchase Price', 
        'Sale Price', 
        'Profit', 
        'Sale Date',
        'Sale Type' 
    ])

    sold_assets = Asset.objects.filter(status='SOLD').select_related(
        'asset_type', 'mixed_sale', 'sale_record'
    ).order_by('pk')

    for asset in sold_assets:
        sale_date = None
        sale_type = None
        
        if asset.mixed_sale:
            sale_date = asset.mixed_sale.sale_date.strftime('%Y-%m-%d')
            sale_type = 'Mixed'
        elif asset.sale_record:
            sale_date = asset.sale_record.sale_date.strftime('%Y-%m-%d')
            sale_type = 'Bulk'

        # Note: Assumes asset.profit_loss property is defined on the HardwareAsset model
        writer.writerow([
            asset.pk,
            asset.asset_type.name if asset.asset_type else '',
            asset.model_number,
            asset.serial_number,
            asset.get_status_display(),
            asset.purchase_price,
            asset.individual_sale_price,
            asset.profit_loss, 
            sale_date,
            sale_type
        ])

    return response

@login_required
def asset_type_list_view(request):
    """
    Displays a list of all defined Asset Types.
    """
    asset_types = AssetType.objects.all().order_by('name')
    
    context = {
        'asset_types': asset_types,
        'title': 'Manage Asset Types'
    }
    return render(request, 'inventory/asset_type_list.html', context)