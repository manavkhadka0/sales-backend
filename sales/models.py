from django.db import models
from account.models import Logistics
from django.utils import timezone
import uuid
import random
import string
# Create your models here.


class Location(models.Model):
    name = models.CharField(max_length=100)
    coverage_areas = models.JSONField(default=list)  # Stores list of strings

    def __str__(self):
        return self.name


class Inventory(models.Model):
    STATUS_CHOICES = [
        ('incoming', 'Incoming'),
        ('raw_material', 'Raw Material'),
        ('ready_to_dispatch', 'Ready to Dispatch'),
        ('damaged_returned', 'Damaged/Returned')
    ]
    distributor = models.ForeignKey(
        'account.Distributor', on_delete=models.CASCADE, null=True, blank=True, related_name='inventory')
    franchise = models.ForeignKey(
        'account.Franchise', on_delete=models.CASCADE, null=True, blank=True, related_name='inventory')
    factory = models.ForeignKey('account.Factory', on_delete=models.CASCADE,
                                null=True, blank=True, related_name='inventory')
    product = models.ForeignKey(
        'sales.Product', on_delete=models.CASCADE, related_name='inventory')
    status = models.CharField(max_length=255, choices=STATUS_CHOICES,
                              default='ready_to_dispatch', null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"


class InventoryChangeLog(models.Model):
    inventory = models.ForeignKey(
        Inventory, on_delete=models.SET_NULL, null=True, related_name='change_logs')
    user = models.ForeignKey(
        'account.CustomUser', on_delete=models.CASCADE, related_name='inventory_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    old_quantity = models.PositiveIntegerField()
    new_quantity = models.PositiveIntegerField()
    action = models.CharField(max_length=20, default='update', choices=[
        ('add', 'Add'),
        ('update', 'Update'),
        ('deleted', 'Deleted'),
        # Added new choice for order creation
        ('order_created', 'Order Created'),
        # Added new choice for order cancellation
        ('order_cancelled', 'Order Cancelled'),

    ])

    def __str__(self):
        product_name = self.inventory.product.name if self.inventory else "Unknown Product"
        # Get inventory organization
        org_name = None
        if self.inventory:
            if self.inventory.factory:
                org_name = f"Factory: {self.inventory.factory}"
            elif self.inventory.distributor:
                org_name = f"Distributor: {self.inventory.distributor}"
            elif self.inventory.franchise:
                org_name = f"Franchise: {self.inventory.franchise}"
        org_str = f" ({org_name})" if org_name else ""

        # Get user role and organization
        user_role = self.user.role if hasattr(
            self.user, 'role') else "Unknown Role"
        user_org = ""
        if hasattr(self.user, 'factory'):
            user_org = f"Factory: {self.user.factory}"
        elif hasattr(self.user, 'distributor'):
            user_org = f"Distributor: {self.user.distributor}"
        elif hasattr(self.user, 'franchise'):
            user_org = f"Franchise: {self.user.franchise}"

        return f"{self.action.title()} - {product_name}{org_str}: {self.old_quantity} → {self.new_quantity} by {self.user.first_name} ({user_role} at {user_org})"


class InventoryRequest(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected')
    )
    factory = models.ForeignKey(
        'account.Factory', on_delete=models.CASCADE, null=True, blank=True)
    distributor = models.ForeignKey(
        'account.Distributor', on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey('account.CustomUser',
                             on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey('sales.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    status = models.CharField(
        max_length=255, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.product} - {self.quantity}"


class Product(models.Model):
    name = models.CharField(max_length=255)
    image = models.FileField(upload_to='products/', blank=True, null=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class OrderProduct(models.Model):
    order = models.ForeignKey(
        'Order', on_delete=models.CASCADE, related_name='order_products')
    product = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.product.product.name} - {self.quantity}"


class PromoCode(models.Model):
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True)  # e.g., 10.00 for 10%
    valid_from = models.DateField(blank=True, null=True)
    valid_until = models.DateField(blank=True, null=True)
    max_uses = models.PositiveIntegerField(
        default=0, blank=True, null=True)  # 0 means unlimited
    times_used = models.PositiveIntegerField(default=0, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.discount_percentage}%"


def generate_order_id():
    """
    Generate a shorter unique order ID
    Format: ORD-XXXXXXXX (first 8 characters from UUID)
    """
    uuid_str = str(uuid.uuid4()).replace('-', '').upper()
    return f"ORD-{uuid_str[:8]}"


class Order(models.Model):
    PAYMENT_CHOICES = [
        ('Cash on Delivery', 'Cash on Delivery'),
        ('Prepaid', 'Prepaid'),
        ('Office Visit', 'Office Visit'),
        ('Indrive', 'Indrive')
    ]

    ORDER_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Verified', 'Verified'),
        ('Sent to Dash', 'Sent to Dash'),
        ('Sent to YDM', 'Sent to YDM'),
        ('Delivered', 'Delivered'),
        ('Indrive', 'Indrive'),
        ('Cancelled', 'Cancelled'),
        ('Returned By Customer', 'Returned By Customer'),
        ('Returned By Dash', 'Returned By Dash'),
        ('Returned By YDM', 'Returned By YDM'),
        ('Return Pending', 'Return Pending'),
        ('Out For Delivery', 'Out For Delivery'),
        ('Rescheduled', 'Rescheduled'),
    ]
    DELIVERY_ADDRESS_CHOICES = [
        ('Inside valley', 'Inside valley'),
        ('Outside valley', 'Outside valley'),
    ]
    LOGISTICS_CHOICES = [
        ('YDM', 'YDM'),
        ('DASH', 'DASH'),
        ('Pick and Drop', 'Pick and Drop'),
        ('NCM', 'NCM'),
    ]
    order_code = models.CharField(
        max_length=20, default=generate_order_id, null=True, blank=True)
    franchise = models.ForeignKey(
        'account.Franchise', on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    distributor = models.ForeignKey(
        'account.Distributor', on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    factory = models.ForeignKey(
        'account.Factory', on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    sales_person = models.ForeignKey(
        'account.CustomUser', on_delete=models.CASCADE, related_name='orders')
    dash_location = models.ForeignKey(
        'sales.Location', on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    full_name = models.CharField(max_length=200)
    city = models.CharField(max_length=200, blank=True)
    delivery_address = models.CharField(max_length=200)
    landmark = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20)
    alternate_phone_number = models.CharField(max_length=20, blank=True)
    payment_method = models.CharField(max_length=255, choices=PAYMENT_CHOICES)
    payment_screenshot = models.FileField(
        upload_to='payment_screenshots/', blank=True, null=True)
    order_status = models.CharField(
        max_length=255, choices=ORDER_STATUS_CHOICES, default='Pending')
    commission_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    delivery_charge = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    delivery_type = models.CharField(
        max_length=255, choices=DELIVERY_ADDRESS_CHOICES, blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    prepaid_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    remarks = models.TextField(blank=True)
    promo_code = models.ForeignKey(
        PromoCode, on_delete=models.SET_NULL, null=True, blank=True)
    logistics = models.CharField(
        max_length=255, choices=LOGISTICS_CHOICES, default='YDM', null=True, blank=True)
    dash_tracking_code = models.CharField(
        max_length=255, blank=True, null=True)

    def __str__(self):
        return f'{self.full_name} - {self.order_status}'

    def save(self, *args, **kwargs):
        if not self.order_code:
            self.order_code = generate_order_id()
        super().save(*args, **kwargs)


class Commission(models.Model):
    sales_person = models.ForeignKey(
        'account.CustomUser', on_delete=models.CASCADE, related_name='commissions')
    franchise = models.ForeignKey(
        'account.Franchise', on_delete=models.CASCADE, related_name='commissions')
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sales_person} - {self.franchise} - ₹{self.rate}"


class DatabaseMode(models.Model):
    demo_data = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.pk = 1  # Enforce singleton
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # Prevent deletion

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]
