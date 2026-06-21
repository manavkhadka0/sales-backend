# models.py
from django.db import models

from account.models import Franchise


class DarazSellerStore(models.Model):
    # Link it to your app's user if necessary
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE)

    # OAuth Tokens
    access_token = models.CharField(max_length=500)
    refresh_token = models.CharField(max_length=500)

    # Expiry timestamps or durations
    access_token_expires_at = models.DateTimeField()
    refresh_token_expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.franchise.name}"
