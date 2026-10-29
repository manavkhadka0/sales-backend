from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from offlineSales.models import OfflineOrder, OfflinePaymentHistory


def record_order_payment(
    order: OfflineOrder,
    amount: Decimal,
    payment_method: str,
    payment_screenshot=None,
    remarks: str = None,
    user=None,
) -> OfflinePaymentHistory:
    """
    Records an incremental payment against an offline order:
    1. Validates that the order is active and has outstanding credit.
    2. Validates payment amount against remaining amount.
    3. Creates OfflinePaymentHistory record.
    4. Updates order paid_amount, remaining_amount, and payment_status atomically.
    """
    if amount <= Decimal("0.00"):
        raise ValidationError({"amount": "Payment amount must be greater than zero."})

    with transaction.atomic():
        locked_order = OfflineOrder.objects.select_for_update().get(id=order.id)

        if locked_order.order_status == OfflineOrder.OrderStatus.CANCELLED:
            raise ValidationError({
                "order": "Cannot record payment for a cancelled order."
            })

        if locked_order.remaining_amount <= Decimal("0.00"):
            raise ValidationError({
                "order": "This order is already fully paid. No remaining credit balance."
            })

        if amount > locked_order.remaining_amount:
            raise ValidationError({
                "amount": (
                    f"Payment amount (Rs. {amount}) exceeds remaining credit balance "
                    f"(Rs. {locked_order.remaining_amount})."
                )
            })

        payment = OfflinePaymentHistory.objects.create(
            customer=locked_order.customer,
            order=locked_order,
            amount=amount,
            payment_method=payment_method,
            payment_screenshot=payment_screenshot,
            remarks=remarks,
            recorded_by=user,
        )

        locked_order.paid_amount += amount
        locked_order.recalculate_payment_status()
        locked_order.save(
            update_fields=[
                "paid_amount",
                "remaining_amount",
                "payment_status",
                "updated_at",
            ]
        )

        return payment
