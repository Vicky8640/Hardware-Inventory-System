# inventory/models.py
from django.db import models
from decimal import Decimal
# --- 1. Asset Types Model ---
class AssetType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    prefix = models.CharField(max_length=10, unique=True, default='AS') # <--- ADD THIS FIELD
    image = models.ImageField(upload_to='asset_type_images/',
                              null=True,
                              blank=True)

    def __str__(self):
        return self.name

# --- 2. Hardware Asset Model ---
class HardwareAsset(models.Model):
    LOCATION_CHOICES = (
        ('GITHURAI_45', 'Githurai 45'),
        ('KIRIGITI', 'Kirigiti'),
        ('KIAMBU', 'Kiambu'),
    )
    STATUS_CHOICES = [
        ('IN_STOCK', 'In Stock'),
        ('PENDING_SALE', 'Pending Sale'),
        ('SOLD', 'Sold'),
        ('SCRAPPED', 'Scrapped'),
    ]

    # --- Core Inventory Fields ---
    asset_type = models.ForeignKey(AssetType, on_delete=models.PROTECT)
    model_number = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_date = models.DateField(auto_now_add=True)

    location = models.CharField(max_length=20, choices=LOCATION_CHOICES, default='KIRIGITI')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_STOCK')
    warranty_end_date = models.DateField(null=True, blank=True)
    
    # --- Sale Tracking Fields (Refactored/Added) ---
    
    sale_record = models.ForeignKey(
        'SaleRecord', # Assuming SaleRecord is defined in this file (or importable)
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        # related_name is optional, but helps. If you remove it, the reverse name is 'salerecord_set'
        related_name='sold_assets' 
    )
    
    # Field to store the final price this specific unit was sold for
    individual_sale_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # This field seems redundant with individual_sale_price if status='SOLD'
    # pending_sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # If you still use it for 'PENDING_SALE' status, keep it, but it's often cleaner to remove it.
    
    # --- Properties ---
    @property
    def auto_serial_number(self):
        # NOTE: This implementation relies on the asset_type.prefix field
        prefix = self.asset_type.prefix if self.asset_type and self.asset_type.prefix else 'AS'
        return f"{prefix}-{self.pk:05d}"
    
    @property
    def sale_price(self):
        """Returns the final sale price if sold, or N/A."""
        if self.status == 'SOLD' and self.individual_sale_price is not None:
            return self.individual_sale_price
        return None
        
    @property
    def profit_loss(self):
        """Calculates profit or loss based on final sale price and purchase price."""
        if self.sale_price is not None:
            return self.sale_price - self.purchase_price
        return None

    def __str__(self):
        if self.serial_number:
            return f"{self.model_number} - {self.serial_number}"
        return f"{self.model_number} - {self.auto_serial_number}"
        
    class Meta:
        # Add any Meta options you need here
        pass

# --- 3. Maintenance Log Model ---
class MaintenanceLog(models.Model):
    asset = models.ForeignKey(HardwareAsset, on_delete=models.CASCADE)
    log_date = models.DateField()
    log_type = models.CharField(max_length=50)
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"Log for {self.asset.serial_number} on {self.log_date}"


class SaleRecord(models.Model):
    SALE_TYPE_CHOICES = [
        ('BULK', 'Quick Bulk Sale'),
        ('MIXED', 'Mixed Item Sale'),
        ('SINGLE', 'Single Asset Sale'),
    ]
    
    sale_type = models.CharField(
        max_length=10, 
        choices=SALE_TYPE_CHOICES, 
        default='MIXED'
    )
    sale_date = models.DateTimeField(auto_now_add=True)
    
    # Store the total amount received for the entire transaction (bulk or mixed cart)
    total_sale_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00
    )
    
    # Total purchase cost of all assets involved in this sale
    total_purchase_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00
    )
    
    # Optional: Link to a Customer model if you implement one
    # customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Sale Record"
        verbose_name_plural = "Sale Records"
        
    def __str__(self):
        return f"Sale {self.pk} - {self.sale_type} on {self.sale_date.strftime('%Y-%m-%d')}"
        
    @property
    def profit_loss(self):
        # Calculate profit/loss for the entire transaction
        return self.total_sale_price - self.total_purchase_cost
