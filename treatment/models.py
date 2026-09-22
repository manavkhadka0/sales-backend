from django.conf import settings
from django.db import models
from django.db.models import Sum

from core.utils.s3bucket import PublicMediaStorage


class TreatmentType(models.TextChoices):
    PACKAGE_MEMBER = "package_member", "Package Member"
    BOTTLE_MEMBER = "bottle_member", "Bottle Member"
    HOME_OIL = "home_oil", "Home Oil"
    ONE_TIME_SERVICE = "one_time_service", "One Time Service"
    FREE_SERVICE = "free_service", "Free Service"


class PackageChoice(models.TextChoices):
    ONE_MONTH = "one_month", "1 Month - Rs. 5000"
    TWO_MONTH = "two_month", "2 Month - Rs. 8000"
    THREE_MONTH = "three_month", "3 Month - Rs. 12000"


PACKAGE_PRICES = {
    PackageChoice.ONE_MONTH: 5000,
    PackageChoice.TWO_MONTH: 8000,
    PackageChoice.THREE_MONTH: 12000,
}


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    ONLINE = "online", "Online"


class CustomerTreatment(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=255, db_index=True)
    address = models.CharField(max_length=255, null=True, blank=True)

    treatment_type = models.CharField(
        max_length=50,
        choices=TreatmentType.choices,
        default=TreatmentType.ONE_TIME_SERVICE,
        db_index=True,
    )
    package = models.CharField(
        max_length=50, choices=PackageChoice.choices, null=True, blank=True
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total fee to be paid for the treatment",
    )
    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount paid on customer registration",
    )
    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        null=True,
        blank=True,
        help_text="Payment method (Cash, Online)",
    )
    reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for providing free service",
    )
    franchise = models.ForeignKey(
        "account.Franchise",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_treatments",
        db_index=True,
    )
    service_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_treatments",
        db_index=True,
    )
    payment_screenshot = models.FileField(
        upload_to="treatment/payments/",
        null=True,
        blank=True,
        storage=PublicMediaStorage(),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["treatment_type", "created_at"]),
            models.Index(fields=["service_by", "treatment_type"]),
            models.Index(fields=["franchise", "treatment_type"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_treatment_type_display()}"

    @property
    def calculated_total_amount(self):
        if self.treatment_type == TreatmentType.FREE_SERVICE:
            return 0.0
        if (
            self.treatment_type == TreatmentType.PACKAGE_MEMBER
            and self.package
            and self.package in PACKAGE_PRICES
        ):
            return float(PACKAGE_PRICES[self.package])
        if self.total_amount is not None:
            return float(self.total_amount)
        if self.package and self.package in PACKAGE_PRICES:
            return float(PACKAGE_PRICES[self.package])
        return 0.0

    @property
    def total_paid(self):
        aggregate = self.payment_history.aggregate(total=Sum("amount"))
        paid = aggregate["total"]
        if paid is not None and float(paid) > 0:
            return float(paid)
        if self.paid_amount is not None:
            return float(self.paid_amount)
        return 0.0

    @property
    def due_amount(self):
        if self.treatment_type == TreatmentType.FREE_SERVICE:
            return 0.0
        total = self.calculated_total_amount
        paid = self.total_paid
        return max(0.0, total - paid)

    @property
    def payment_status(self):
        if self.treatment_type == TreatmentType.FREE_SERVICE:
            return "Free"
        total = self.calculated_total_amount
        paid = self.total_paid
        if total > 0 and paid >= total:
            return "Paid"
        elif paid > 0:
            return "Partial"
        return "Pending"


class Image(models.Model):
    customer_treatment = models.ForeignKey(
        CustomerTreatment, on_delete=models.CASCADE, related_name="images"
    )
    day_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Day number for periodic treatment tracking (e.g., Day 1, Day 4, Day 8)",
    )
    image = models.FileField(
        upload_to="treatment/images/",
        null=True,
        blank=True,
        storage=PublicMediaStorage(),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_number", "created_at"]
        indexes = [
            models.Index(fields=["customer_treatment", "day_number"]),
        ]

    def __str__(self):
        day_str = f" Day {self.day_number}" if self.day_number else ""
        return f"{self.customer_treatment.name} - {day_str}"


class PaymentHistory(models.Model):
    customer_treatment = models.ForeignKey(
        CustomerTreatment, on_delete=models.CASCADE, related_name="payment_history"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=50,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE,
        db_index=True,
    )
    payment_screenshot = models.FileField(
        upload_to="treatment/payments/",
        null=True,
        blank=True,
        storage=PublicMediaStorage(),
    )
    remarks = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="treatment_payments_recorded",
    )
    payment_date = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date"]
        indexes = [
            models.Index(fields=["customer_treatment", "payment_date"]),
        ]

    def __str__(self):
        return f"{self.customer_treatment.name} - Rs. {self.amount} ({self.get_payment_method_display()})"
