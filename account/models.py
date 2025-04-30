from django.db import models
from django.contrib.auth.models import AbstractUser


class Factory(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    short_form = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class Distributor(models.Model):
    factory = models.ForeignKey(
        Factory, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    short_form = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class Franchise(models.Model):
    distributor = models.ForeignKey(
        Distributor, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    short_form = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('SuperAdmin', 'Super Admin'),
        ('Distributor', 'Distributor'),
        ('Franchise', 'Franchise'),
        ('SalesPerson', 'Sales Person'),
        ('Others', 'Others')
    )
    phone_number = models.CharField(max_length=20)
    address = models.TextField()
    distributor = models.ForeignKey(
        Distributor, on_delete=models.CASCADE, null=True, blank=True)
    franchise = models.ForeignKey(
        Franchise, on_delete=models.CASCADE, null=True, blank=True)
    factory = models.ForeignKey(
        Factory, on_delete=models.CASCADE, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    commission_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def soft_delete(self):
        self.is_active = False
        self.save()

    def __str__(self):
        return f"{self.username}"
