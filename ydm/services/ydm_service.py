import logging

from django.conf import settings
from rest_framework.exceptions import ValidationError

from ydm.ydm_sdk import YDMApiError, YDMClient, YDMValidationError

logger = logging.getLogger(__name__)

# Maps sales Order.payment_method values to YDM API payment_type codes.
PAYMENT_TYPE_MAP: dict[str, str] = {
    "Cash on Delivery": "COD",
    "Prepaid": "Prepaid",
}


def _build_order_payload(order) -> dict:
    """
    Build the YDM API payload from a sales Order instance.
    """
    products = [
        {
            "name": op.product.product.name,
            "quantity": op.quantity,
        }
        for op in order.order_products.select_related("product__product").all()
    ]

    payment_type = PAYMENT_TYPE_MAP.get(order.payment_method, order.payment_method)

    return {
        "external_order_code": order.order_code or "",
        "recipient_name": order.full_name,
        "recipient_phone": order.phone_number,
        "recipient_address": order.delivery_address,
        "recipient_city": order.city or "",
        "cod_amount": float(order.total_amount or 0),
        "delivery_charge": float(order.delivery_charge or 0),
        "payment_type": payment_type,
        "product": products,
        "remarks": order.remarks or "",
    }


def push_order_to_ydm(order) -> dict:
    """
    Synchronously push a sales Order to the YDM Logistics system.

    Looks up the YDMLogistics config for the order's franchise, builds the
    payload, and calls the YDM SDK.

    Returns the YDM API response dict on success.
    Raises rest_framework.exceptions.ValidationError on any failure so the
    caller's HTTP response reflects the error and no DB changes are committed.
    """
    from ydm.models import YDMLogistics

    base_url: str = getattr(settings, "YDM_BASE_URL", "")
    print(
        f"[YDM] push_order_to_ydm called — order pk={order.pk}, base_url='{base_url}'"
    )

    if not base_url:
        raise ValidationError(
            "YDM_BASE_URL is not configured. Cannot send order to YDM."
        )

    franchise = order.franchise
    if franchise is None:
        raise ValidationError("Order has no franchise assigned. Cannot send to YDM.")

    try:
        ydm_config = YDMLogistics.objects.get(franchise=franchise)
        print(
            f"[YDM] Config found — franchise='{franchise}', api_key={ydm_config.api_key!r}"
        )
    except YDMLogistics.DoesNotExist:
        raise ValidationError(
            f"No YDM Logistics configuration found for franchise '{franchise}'. "
            "Please set up the YDM API key before sending orders."
        )

    payload = _build_order_payload(order)
    print(f"[YDM] Payload: {payload}")

    client = YDMClient(base_url=base_url, api_key=ydm_config.api_key)

    try:
        response = client.create_order(payload)
        print(f"[YDM] ✅ Success — tracking: {response.get('tracking_number')}")
        logger.info(
            "Order pk=%s pushed to YDM. Tracking: %s",
            order.pk,
            response.get("tracking_number"),
        )
        return response
    except YDMValidationError as exc:
        logger.error("YDM validation error for order pk=%s: %s", order.pk, exc)
        raise ValidationError(f"YDM rejected the order: {exc}")
    except YDMApiError as exc:
        logger.error("YDM API error for order pk=%s: %s", order.pk, exc)
        raise ValidationError(f"YDM API error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected YDM error for order pk=%s: %s", order.pk, exc)
        raise ValidationError(f"Unexpected error sending order to YDM: {exc}")
