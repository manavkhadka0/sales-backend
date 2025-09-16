from django.db import models
from django.utils import timezone
from sales.models import Order
from account.models import CustomUser


class Organization(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    logo = models.FileField(upload_to='organizations/', blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Sales(models.Model):
    sales_count = models.IntegerField(default=0)
    date = models.DateField(
        auto_now=False, auto_created=False, auto_now_add=False)
    lucky_draw_system = models.ForeignKey(
        'LuckyDrawSystem', on_delete=models.CASCADE, related_name='sales')

    def __str__(self):
        return str(self.sales_count)


class LuckyDrawSystem(models.Model):
    LUCKY_DRAW_TYPE_CHOICES = [
        ('Mobile Phone Brand', 'Mobile Phone Brand'),
        ('Electronics Shop', 'Electronics Shop'),
        ('Other Shop', 'Other Shop'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    background_image = models.FileField(
        upload_to='lucky_draws/', blank=True, null=True)
    hero_image = models.FileField(
        upload_to='lucky_draws/', blank=True, null=True)
    main_offer_stamp_image = models.FileField(
        upload_to='lucky_draws/', blank=True, null=True)
    hero_title = models.CharField(max_length=255, default='')
    hero_subtitle = models.CharField(max_length=255, default='')
    qr = models.FileField(upload_to='lucky_draws/', blank=True, null=True)
    type = models.CharField(max_length=20, choices=LUCKY_DRAW_TYPE_CHOICES)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    start_date = models.DateField()
    end_date = models.DateField()
    uuid_key = models.CharField(max_length=255, unique=True, default='')
    how_to_participate = models.TextField(blank=True)
    redeem_condition = models.TextField(blank=True)
    terms_and_conditions = models.TextField(blank=True)

    def __str__(self):
        return self.name


class GiftItem(models.Model):
    GIFT_CATEGORY_CHOICES = [
        ('minor', 'Minor Gift'),
        ('major', 'Major Gift'),
        ('grand', 'Grand Gift'),
    ]

    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem, on_delete=models.CASCADE, related_name='gift_items')
    name = models.CharField(max_length=255)
    image = models.FileField(upload_to='gift_items/', blank=True, null=True)
    category = models.CharField(
        max_length=10, choices=GIFT_CATEGORY_CHOICES, default='minor', null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.category}"


class RechargeCard(models.Model):
    AMOUNT_CHOICES = [(50, "50"), (100, "100"), (200, "200"), (500, "500")]
    PROVIDER_CHOICES = [
        ("Ncell", "Ncell"),
        ("Ntc", "Ntc"),
        ("Smart Cell", "Smart Cell"),
        ("Others", "Others"),
    ]
    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem, on_delete=models.CASCADE, related_name='recharge_cards')
    cardno = models.CharField(max_length=400, unique=True)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    amount = models.IntegerField(choices=AMOUNT_CHOICES)
    is_assigned = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.provider} - {self.cardno}"


class IMEINO(models.Model):
    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem, on_delete=models.CASCADE, related_name='imei_numbers')
    imei_no = models.CharField(max_length=400, unique=True)
    phone_model = models.CharField(max_length=400, blank=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return self.imei_no


class FixOffer(models.Model):
    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem, on_delete=models.CASCADE, related_name='fix_offers')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    imei_no = models.CharField(max_length=400, blank=True, null=True)
    quantity = models.PositiveIntegerField()
    gift = models.ManyToManyField(GiftItem, blank=True)

    def __str__(self):
        gift_names = ", ".join([g.name for g in self.gift.all()])
        return f"{self.imei_no} - {gift_names}"


class BaseOffer(models.Model):
    OFFER_CHOICES = [
        ("After every certain sale", "After every certain sale"),
        ("At certain sale position", "At certain sale position")
    ]

    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem, on_delete=models.CASCADE)
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


class MobileOfferCondition(models.Model):
    offer_condition_name = models.CharField(max_length=100)
    condition = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.offer_condition_name} (Condition: {self.condition})"


class MobilePhoneOffer(BaseOffer):
    gift = models.ForeignKey(GiftItem, on_delete=models.CASCADE)
    valid_condition = models.ManyToManyField(MobileOfferCondition, blank=True)
    priority = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Offer on {self.gift.name}"

    class Meta:
        ordering = ("start_date", "priority")


class RechargeCardCondition(models.Model):
    offer_condition_name = models.CharField(max_length=100)
    condition = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.offer_type_name} (Condition: {self.condition})"


class RechargeCardOffer(BaseOffer):
    amount = models.IntegerField(
        choices=RechargeCard.AMOUNT_CHOICES, default=50)
    provider = models.CharField(
        max_length=20, choices=RechargeCard.PROVIDER_CHOICES, default="Ncell")
    valid_condition = models.ManyToManyField(RechargeCardCondition, blank=True)

    def __str__(self):
        return f"Offer on {self.provider} of {self.amount} Recharge card [ {self.quantity} ]"

    class Meta:
        ordering = ("start_date",)


class ElectronicOfferCondition(models.Model):
    offer_condition_name = models.CharField(max_length=100)
    condition = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.offer_type_name} (Condition: {self.condition})"


class ElectronicsShopOffer(BaseOffer):
    gift = models.ManyToManyField(GiftItem, blank=True)
    valid_condition = models.ManyToManyField(
        ElectronicOfferCondition, blank=True)

    def __str__(self):
        gift_names = ", ".join([g.name for g in self.gift.all()])
        return f"Offer on {gift_names} Electronics Shop [ {self.daily_quantity} ]"

    class Meta:
        ordering = ("start_date",)


class Customer(models.Model):

    lucky_draw_system = models.ForeignKey(
        LuckyDrawSystem, on_delete=models.CASCADE, related_name='customers')
    full_name = models.CharField(max_length=255, blank=True, null=True)
    gift = models.ManyToManyField(
        GiftItem, blank=True)
    prize_details = models.CharField(max_length=900, default="Thank You")
    date_of_purchase = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.full_name

    class Meta:
        ordering = ("-date_of_purchase",)
