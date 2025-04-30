from django.db import models

# Create your models here.


class CustomerTreatment(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Image(models.Model):
    STATUS_CHOICES = (
        ('Before', 'Before'),
        ('After', 'After'),
    )
    customer_treatment = models.ForeignKey(
        CustomerTreatment, on_delete=models.CASCADE, related_name='images')
    status = models.CharField(
        max_length=255, choices=STATUS_CHOICES, default='Before')
    image = models.FileField(
        upload_to='treatment/images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.image.name
