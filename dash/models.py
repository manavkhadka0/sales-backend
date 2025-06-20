from django.db import models
from account.models import CustomUser, Franchise

# Create your models here.


class Dash(models.Model):
    franchise = models.ForeignKey(
        Franchise, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(max_length=255)
    password = models.CharField(max_length=255)
    client_id = models.IntegerField(null=True, blank=True)
    client_secret = models.CharField(max_length=255, null=True, blank=True)
    grant_type = models.CharField(max_length=255, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    access_token = models.CharField(max_length=255, null=True, blank=True)
    refresh_token = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email
