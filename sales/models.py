from django.db import models

# Create your models here.

class Inventory(models.Model):
    STATUS_CHOICES = [
        ('incoming', 'Incoming'),
        ('ready_to_dispatch', 'Ready to Dispatch'),
        ('damaged_returned', 'Damaged/Returned')
    ]
    distributor = models.ForeignKey('account.Distributor', on_delete=models.CASCADE, null=True, blank=True, related_name='inventory')
    franchise= models.ForeignKey('account.Franchise', on_delete=models.CASCADE, null=True, blank=True, related_name='inventory')
    factory = models.ForeignKey('account.Factory', on_delete=models.CASCADE, null=True, blank=True, related_name='inventory')
    product = models.ForeignKey('sales.Product', on_delete=models.CASCADE, related_name='inventory')
    status = models.CharField(max_length=255, choices=STATUS_CHOICES, default='incoming',null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"

class InventoryChangeLog(models.Model):
    inventory = models.ForeignKey(Inventory, on_delete=models.SET_NULL, null=True, related_name='change_logs')
    user = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE, related_name='inventory_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    old_quantity = models.PositiveIntegerField()
    new_quantity = models.PositiveIntegerField()
    action = models.CharField(max_length=20, default='update', choices=[
        ('add', 'Add'),
        ('update', 'Update'),
        ('deleted', 'Deleted'),
    ])

    def __str__(self):
        return f"Change by {self.user.username} on {self.changed_at}: {self.old_quantity} -> {self.new_quantity}"

class InventoryRequest(models.Model):
    STATUS_CHOICES=(
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected')
    )
    user = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE,null=True, blank=True)
    product = models.ForeignKey('sales.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    status = models.CharField(max_length=255, choices=STATUS_CHOICES,default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.product} - {self.quantity}"
    

class Product(models.Model):
    name = models.CharField(max_length=255)
    image=models.FileField(upload_to='products/',blank=True,null=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class OrderProduct(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='order_products')
    product = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product.product.name} - {self.quantity}"

class Order(models.Model):
    PAYMENT_CHOICES = [
        ('Cash on Delivery', 'Cash on Delivery'),
        ('Prepaid', 'Prepaid')
    ]

    ORDER_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled')
    ]
    franchise = models.ForeignKey('account.Franchise', on_delete=models.CASCADE, related_name='orders')
    sales_person = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE, related_name='orders')
    full_name = models.CharField(max_length=200)
    city = models.CharField(max_length=200, blank=True)
    delivery_address = models.CharField(max_length=200)
    landmark = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20)
    alternate_phone_number = models.CharField(max_length=20, blank=True)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=255, choices=PAYMENT_CHOICES)
    payment_screenshot = models.ImageField(upload_to='payment_screenshots/', blank=True, null=True)
    order_status = models.CharField(max_length=255, choices=ORDER_STATUS_CHOICES, default='Pending')
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    date=models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f'{self.full_name} - {self.order_status}'

class Commission(models.Model):
    sales_person = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE, related_name='commissions')
    franchise = models.ForeignKey('account.Franchise', on_delete=models.CASCADE, related_name='commissions')
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    paid=models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sales_person} - {self.franchise} - ₹{self.rate}"

