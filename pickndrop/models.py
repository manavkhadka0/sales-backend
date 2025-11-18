from django.db import models


# Create your models here.
class PickNDrop(models.Model):
    franchise = models.ForeignKey(
        "account.Franchise", on_delete=models.CASCADE, null=True, blank=True
    )
    email = models.EmailField(max_length=255, null=True, blank=True)
    password = models.CharField(max_length=255, null=True, blank=True)
    client_key = models.CharField(max_length=255, null=True, blank=True)
    client_secret = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
