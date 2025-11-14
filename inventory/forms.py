# inventory/forms.py

from django import forms
# NOTE: Ensure HardwareAsset, AssetType, and SaleRecord are imported from the correct location
# Assuming they are in the same directory's models.py:
from .models import HardwareAsset, AssetType, SaleRecord, MaintenanceLog 
# You might need to import your SaleRecord model here if a form is related to it

# --- 1. Form for Adding New Assets ---
class AssetForm(forms.ModelForm):
    model_number = forms.CharField(max_length=100, required=True, 
                                   widget=forms.TextInput(attrs={'placeholder': 'e.g., LAP-100'}))

    quantity = forms.IntegerField(min_value=1, initial=1)

    class Meta:
        model = HardwareAsset
        fields = [
            'asset_type', 
            'model_number', 
            'purchase_price', 
            'location', 
            'warranty_end_date',
        ]
        widgets = {
            'purchase_price': forms.NumberInput(attrs={'step': '0.01'}),
            'warranty_end_date': forms.DateInput(attrs={'type': 'date'}),
        }

# --- 2. Form for Quick Bulk Sale ---
class BulkSaleForm(forms.Form):
    # Existing fields
    asset_type = forms.ModelChoiceField(
        # FIX: Provide a valid queryset
        queryset=AssetType.objects.all().order_by('name'), 
        label="Asset Type to Sell:",
        empty_label="-----------", # Optional: Ensures a clean starting state
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        label="Quantity to Sell",
        help_text="Enter the number of assets to sell (must be in stock).",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )
    
    unit_sale_price = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        min_value=0.01,
        label="Sale Price (Per Unit)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    location = forms.ChoiceField(
        choices=HardwareAsset.LOCATION_CHOICES,
        label="Location to Sell From",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

# --- 3. Form for Asset Filtering (Inventory List) ---
class AssetFilterForm(forms.Form):
    asset_type = forms.ModelChoiceField(
        queryset=AssetType.objects.all().order_by('name'),
        required=False,
        label='Filter by Type',
        empty_label='-- All Types --',
        widget=forms.Select(attrs={'class': 'form-select'}) 
    )
    
    status = forms.ChoiceField(
        choices=[('', '-- All Statuses --')] + list(HardwareAsset.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    location = forms.ChoiceField(
        choices=[('', '-- All Locations --')] + list(HardwareAsset.LOCATION_CHOICES), 
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

# --- 4. Form for Mixed Sale Finalization (The Checkout) ---
class MixedSaleForm(forms.Form):
    sale_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))
    # Add other fields here as needed later, ensuring no ModelChoiceField uses '...'

# --- 5. Clean Placeholder Form (If needed for other views) ---
class AssetUpdateForm(forms.ModelForm):
    class Meta:
        model = HardwareAsset
        fields = ['status', 'location', 'warranty_end_date']
    # Add other fields like customer, sale notes, etc., as needed

# --- NEW FORM DEFINITION ---
class MaintenanceLogForm(forms.ModelForm):
    # Set the asset field to a HiddenInput since its value is passed 
    # automatically from the view (asset_detail_view)
    asset = forms.CharField(widget=forms.HiddenInput())
    
    class Meta:
        model = MaintenanceLog
        fields = ['asset', 'log_date', 'log_type', 'cost', 'description']
        
        widgets = {
            'log_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'log_type': forms.Select(attrs={'class': 'form-select'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        
        labels = {
            'log_date': 'Date Performed',
            'log_type': 'Type of Service',
        }