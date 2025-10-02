from django import forms
from .models import HardwareAsset  # Assuming your asset model is HardwareAsset
class AssetForm(forms.ModelForm):
    # These fields correspond to the inputs in your add_asset_form.html
    # We exclude 'serial_number' and 'status' because they are handled manually/in the view.
    
    # We'll use a standard CharField for the model_number for simplicity
    model_number = forms.CharField(max_length=100, required=True, 
                                   widget=forms.TextInput(attrs={'placeholder': 'e.g., LAP-100'}))

    # The 'quantity' field is for bulk creation, which is handled in the view logic, 
    # but we include it in the form for validation/rendering.
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

from django import forms
from .models import AssetType # Make sure this import is correct

class BulkSaleForm(forms.Form):
    asset_type = forms.ModelChoiceField(
        queryset=AssetType.objects.all().order_by('name'),
        label="Asset Type to Sell",
        help_text="Select the type of asset you are selling in bulk.",
        widget=forms.Select(attrs={'class': 'form-select'}) # Bootstrap style
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        label="Quantity to Sell",
        help_text="Enter the number of assets to sell (must be in stock).",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )
    
    # This is the price PER UNIT
    unit_sale_price = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        min_value=0.01,
        label="Sale Price (Per Unit)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )