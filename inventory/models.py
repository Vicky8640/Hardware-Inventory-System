from django.db import models

# --- 1. Asset Types Model ---
class AssetType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    # New Field for the image
    image = models.ImageField(upload_to='asset_type_images/', 
                              null=True, 
                              blank=True) 

    def __str__(self):
        return self.name
    # ... rest of the model ... 
# --- 2. Hardware Asset Model ---
class HardwareAsset(models.Model):
    LOCATION_CHOICES = (
        ('GITHURAI_45', 'Githurai 45'),
        ('KIRIGITI', 'Kirigiti'),
        ('KIAMBU', 'Kiambu'),
        # Add more locations as needed
    )
    STATUS_CHOICES = [
        ('IN_STOCK', 'In Stock'),
        ('PENDING_SALE', 'Pending Sale'),
        ('SOLD', 'Sold'),
        ('SCRAPPED', 'Scrapped'),
    ]
    pending_sale_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )

    location = models.CharField(
        max_length=20, 
        choices=LOCATION_CHOICES, 
        default='KIRIGITI' # Set a new default if needed
    )

    asset_type = models.ForeignKey(AssetType, on_delete=models.PROTECT) 
    model_number = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True, null=True, blank=True) 
    
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_date = models.DateField(auto_now_add=True) 
    warranty_end_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_STOCK')
    # Property to generate a unique ID if the S/N is blank (used for display)
    @property
    def auto_serial_number(self):
        # Format: ModelCode-AssetID (e.g., LPT-00001, MTR-00002)
        # We can use the first few letters of the model or type name as a prefix
        prefix = self.asset_type.name[:3].upper() if self.asset_type else 'AS'
        return f"{prefix}-{self.pk:05d}" # :05d pads the ID with leading zeros

    def __str__(self):
        # Use the generated S/N if the user didn't provide one
        if self.serial_number:
            return f"{self.model_number} - {self.serial_number}"
        return f"{self.model_number} - {self.auto_serial_number}"
    # We will set the Retirement link later, after defining the AssetRetirementSale model, 
    # as Django sometimes handles cross-references better with strings if defined out of order.
    # We will use a related_name property instead of a FK here for a cleaner OneToOne relationship.

    def __str__(self):
        return f"{self.model_number} - {self.serial_number}"

# --- 3. Maintenance Log Model ---
class MaintenanceLog(models.Model):
    asset = models.ForeignKey(HardwareAsset, on_delete=models.CASCADE) 
    
    log_date = models.DateField()
    log_type = models.CharField(max_length=50) 
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"Log for {self.asset.serial_number} on {self.log_date}"

# --- 4. Asset Retirement/Sale Model ---
class AssetRetirementSale(models.Model):
    # OneToOneField uses 'asset' as the primary key here, linking to HardwareAsset
    asset = models.OneToOneField(HardwareAsset, on_delete=models.CASCADE, primary_key=True, related_name='sale_record')
    
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    retirement_date = models.DateField(auto_now_add=True)
    
    cost_basis = models.DecimalField(max_digits=10, decimal_places=2, editable=False) 
    profit_loss = models.DecimalField(max_digits=10, decimal_places=2, editable=False) 

    def __str__(self):
        return f"Sale of {self.asset.serial_number} - Profit/Loss: {self.profit_loss}"



# NOTE: You will need to run migrations after this change.
# python manage.py makemigrations inventory
# python manage.py migrate