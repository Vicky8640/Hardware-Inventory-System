# inventory/models.py
from django.db import models
from decimal import Decimal # Ensure Decimal is imported for financial accuracy

# --- 1. Asset Types Model ---
class AssetType(models.Model):
    name = models.CharField(max_length=50, unique=True)
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
    
    asset_type = models.ForeignKey(AssetType, on_delete=models.PROTECT) 
    model_number = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True, null=True, blank=True) 
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_date = models.DateField(auto_now_add=True) 
    
    location = models.CharField(max_length=20, choices=LOCATION_CHOICES, default='KIRIGITI')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_STOCK')
    pending_sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)

    @property
    def auto_serial_number(self):
        prefix = self.asset_type.name[:3].upper() if self.asset_type else 'AS'
        return f"{prefix}-{self.pk:05d}"

    def __str__(self):
        if self.serial_number:
            return f"{self.model_number} - {self.serial_number}"
        return f"{self.model_number} - {self.auto_serial_number}"

# --- 3. Maintenance Log Model ---
class MaintenanceLog(models.Model):
    asset = models.ForeignKey(HardwareAsset, on_delete=models.CASCADE) 
    log_date = models.DateField()
    log_type = models.CharField(max_length=50) 
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00')) 
    
    def __str__(self):
        return f"Log for {self.asset.serial_number} on {self.log_date}"

# --- 4. Asset Retirement/Sale Model (CRITICAL CORRECTION HERE) ---
class AssetRetirementSale(models.Model):
    asset = models.OneToOneField(
        HardwareAsset, 
        on_delete=models.CASCADE, 
        primary_key=True, # This makes the Asset ID the primary key for the sale record
        related_name='sale_record'
    )
    
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    retirement_date = models.DateField(auto_now_add=True)
    
    # These fields are non-editable in the admin but calculated on save
    cost_basis = models.DecimalField(max_digits=10, decimal_places=2, editable=False) 
    profit_loss = models.DecimalField(max_digits=10, decimal_places=2, editable=False) 

    def save(self, *args, **kwargs):
        """
        Calculates the cost basis and profit/loss before saving.
        This ensures financial data is accurate and permanent at the time of sale.
        """
        # 1. Get the cost basis from the linked HardwareAsset
        self.cost_basis = self.asset.purchase_price
        
        # 2. Calculate profit/loss
        # Ensure calculation uses Decimal for precision
        self.profit_loss = self.sale_price - self.cost_basis
        
        # 3. Save the instance
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale of {self.asset.serial_number} - Profit/Loss: {self.profit_loss}"