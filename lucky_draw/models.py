from django.db import models
from django.utils import timezone

from account.models import Franchise


class Organization(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    logo = models.FileField(upload_to="organizations/", blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Sales(models.Model):
    sales_count = models.IntegerField(default=0)
    date = models.DateField(auto_now=False, auto_created=False, auto_now_add=False)
    lucky_draw_system = models.ForeignKey(
        "LuckyDrawSystem", on_delete=models.CASCADE, related_name="sales"
    )

    def __str__(self):
        return str(self.sales_count)


class LuckyDrawSystem(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, null=True, blank=True
    )
    franchise = models.ForeignKey(
        Franchise, on_delete=models.CASCADE, null=True, blank=True
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    background_image = models.FileField(upload_to="lucky_draws/", blank=True, null=True)
    hero_image = models.FileField(upload_to="lucky_draws/", blank=True, null=True)
    main_offer_stamp_image = models.FileField(
        upload_to="lucky_draws/", blank=True, null=True
    )
    hero_title = models.CharField(max_length=255, default="")
    hero_subtitle = models.CharField(max_length=255, default="")
    qr = models.FileField(upload_to="lucky_draws/", blank=True, null=True)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    start_date = models.DateField()
    end_date = models.DateField()
    uuid_key = models.CharField(
        max_length=255, unique=True, default="", null=True, blank=True
    )

    def __str__(self):
        return self.name


class GiftItem(models.Model):
    GIFT_CATEGORY_CHOICES = [
        ("minor", "Minor Gift"),
        ("major", "Major Gift"),
        ("grand", "Grand Gift"),
    ]

    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem, on_delete=models.CASCADE, related_name="gift_items"
    )
    name = models.CharField(max_length=255)
    image = models.FileField(upload_to="gift_items/", blank=True, null=True)
    category = models.CharField(
        max_length=10,
        choices=GIFT_CATEGORY_CHOICES,
        default="minor",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name} - {self.category}"


class FixOffer(models.Model):
    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem, on_delete=models.CASCADE, related_name="fix_offers"
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    quantity = models.PositiveIntegerField()
    gift = models.ManyToManyField(GiftItem, blank=True)

    def __str__(self):
        gift_names = ", ".join([g.name for g in self.gift.all()])
        return f"{self.phone_number} - {gift_names}"


class BaseOffer(models.Model):
    OFFER_CHOICES = [
        ("After every certain sale", "After every certain sale"),
        ("At certain sale position", "At certain sale position"),
    ]

    lucky_draw_system = models.ForeignKey(LuckyDrawSystem, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField(default="00:00")
    end_time = models.TimeField(default="23:59")
    has_time_limit = models.BooleanField(default=False)
    daily_quantity = models.PositiveIntegerField(default=0)
    type_of_offer = models.CharField(max_length=30, choices=OFFER_CHOICES)
    offer_condition_value = models.CharField(max_length=500, blank=True)
    sale_numbers = models.JSONField(null=True, blank=True)
    has_region_limit = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def is_valid_date(self):
        return self.start_date <= timezone.now().date() <= self.end_date


class OfferCondition(models.Model):
    offer_condition_name = models.CharField(max_length=100)
    condition = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.offer_type_name} (Condition: {self.condition})"


class Offer(BaseOffer):
    gift = models.ManyToManyField(GiftItem, blank=True)
    valid_condition = models.ManyToManyField(OfferCondition, blank=True)

    def __str__(self):
        gift_names = ", ".join([g.name for g in self.gift.all()])
        return f"Offer on {gift_names} Electronics Shop [ {self.daily_quantity} ]"

    class Meta:
        ordering = ("start_date",)


class Customer(models.Model):
    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem, on_delete=models.CASCADE, related_name="customers"
    )
    full_name = models.CharField(max_length=255, blank=True, null=True)
    gift = models.ManyToManyField(GiftItem, blank=True)
    prize_details = models.CharField(max_length=900, default="Thank You")
    date_of_purchase = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.full_name

    class Meta:
        ordering = ("-date_of_purchase",)
