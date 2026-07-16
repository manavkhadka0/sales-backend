from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sales.models import Order

from .models import YDMLogistics
from .serializers import YDMLogisticsSerializer


class YDMLogisticsListCreateView(generics.ListCreateAPIView):
    serializer_class = YDMLogisticsSerializer
    filter_backends = [DjangoFilterBackend]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.franchise:
            raise PermissionDenied("You do not have an associated franchise.")
        return YDMLogistics.objects.filter(franchise=user.franchise)

    def perform_create(self, serializer):
        user = self.request.user
        if not user.franchise:
            raise PermissionDenied("You do not have an associated franchise.")
        serializer.save(franchise=user.franchise)


class YDMLogisticsRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = YDMLogisticsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.franchise:
            raise PermissionDenied("You do not have an associated franchise.")
        return YDMLogistics.objects.filter(franchise=user.franchise)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.franchise != self.request.user.franchise:
            raise PermissionDenied(
                "You can only change settings for your own franchise."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance.franchise != self.request.user.franchise:
            raise PermissionDenied(
                "You can only delete settings for your own franchise."
            )
        instance.delete()


class YDMWebhookAPIView(APIView):
    """
    Receive webhook notifications from YDM and mirror the status change
    onto the corresponding sales Order.

    YDM sends:
        {
            "event": "order.status_changed",
            "timestamp": "...",
            "data": {
                "tracking_number": "YDM-XXXX",
                "external_order_code": "<order.order_code>",
                "new_status": "DELIVERED",   # YDM status code
                ...
            }
        }
    """

    permission_classes = [AllowAny]

    # Maps YDM status codes → sales Order.order_status values.
    #
    # Full list of YDM statuses the webhook can send:
    #   ORDER_PLACED        – order received by YDM (already "Sent to YDM" on our side)
    #   ORDER_VERIFIED      – YDM has verified the order details
    #   RECEIVED_AT_OFFICE  – parcel collected at YDM office
    #   READY_FOR_DISPATCH  – parcel ready to be dispatched
    #   ORDER_DISPATCHED    – parcel handed off to a rider
    #   OUT_FOR_DELIVERY    – rider is en route
    #   RESCHEDULED         – delivery rescheduled
    #   DELIVERED           – successfully delivered
    #   CANCELLED           – order cancelled
    #   RETURNING_TO_VENDOR – parcel on its way back
    #   RETURNED_TO_VENDOR  – parcel returned to vendor
    #   ON_HOLD             – order placed on hold
    #
    # Early pipeline statuses (ORDER_PLACED … ORDER_DISPATCHED) have no
    # meaningful equivalent in the sales model — they are mapped to None
    # so the webhook is acknowledged but no status change is applied.
    YDM_STATUS_MAP = {
        "ORDER_PLACED": None,  # already "Sent to YDM" when we pushed
        "ORDER_VERIFIED": None,  # no sales equivalent
        "RECEIVED_AT_OFFICE": None,  # no sales equivalent
        "READY_FOR_DISPATCH": None,  # no sales equivalent
        "ORDER_DISPATCHED": None,  # no sales equivalent
        "OUT_FOR_DELIVERY": "Out For Delivery",
        "RESCHEDULED": "Rescheduled",
        "DELIVERED": "Delivered",
        "CANCELLED": "Cancelled",
        "RETURNING_TO_VENDOR": "Return Pending",
        "RETURNED_TO_VENDOR": "Returned By YDM",
        "ON_HOLD": "Rescheduled",
    }

    def post(self, request):
        payload = request.data
        event = payload.get("event", "")
        data = payload.get("data", {})

        external_order_code = data.get("external_order_code", "")
        tracking_number = data.get("tracking_number", "")
        ydm_new_status = data.get("new_status", "")

        print(
            f"[YDM Webhook] event='{event}' | tracking='{tracking_number}' | "
            f"external_code='{external_order_code}' | ydm_status='{ydm_new_status}'"
        )

        # Nothing to act on if status is missing
        if not ydm_new_status:
            print("[YDM Webhook] No new_status in payload — ignoring.")
            return Response({"status": "received"}, status=status.HTTP_200_OK)

        # Translate YDM status → sales status
        # Use sentinel to detect keys that are absent vs explicitly mapped to None
        _MISSING = object()
        sales_new_status = self.YDM_STATUS_MAP.get(ydm_new_status, _MISSING)

        if sales_new_status is _MISSING:
            # Completely unknown status — log and ack
            print(
                f"[YDM Webhook] Unknown YDM status '{ydm_new_status}' — no mapping defined."
            )
            return Response({"status": "received"}, status=status.HTTP_200_OK)

        if sales_new_status is None:
            # Known status intentionally skipped (early pipeline stage)
            print(
                f"[YDM Webhook] Status '{ydm_new_status}' intentionally skipped — no sales equivalent."
            )
            return Response({"status": "received"}, status=status.HTTP_200_OK)

        # Look up the sales order by order_code (= external_order_code sent during push)
        if not external_order_code:
            print("[YDM Webhook] No external_order_code — cannot find order.")
            return Response({"status": "received"}, status=status.HTTP_200_OK)

        try:
            order = Order.objects.get(order_code=external_order_code)
        except Order.DoesNotExist:
            print(
                f"[YDM Webhook] ❌ Order with order_code='{external_order_code}' not found."
            )
            return Response({"status": "received"}, status=status.HTTP_200_OK)
        except Order.MultipleObjectsReturned:
            print(
                f"[YDM Webhook] ⚠️ Multiple orders with order_code='{external_order_code}' — skipping."
            )
            return Response({"status": "received"}, status=status.HTTP_200_OK)

        previous_status = order.order_status

        if previous_status == sales_new_status:
            print(
                f"[YDM Webhook] Order pk={order.pk} already has status '{sales_new_status}' — no change."
            )
            return Response({"status": "received"}, status=status.HTTP_200_OK)

        # Apply the status change
        order.order_status = sales_new_status
        order.save(update_fields=["order_status", "updated_at"])

        print(
            f"[YDM Webhook] ✅ Order pk={order.pk} status updated: "
            f"'{previous_status}' → '{sales_new_status}'"
        )

        return Response({"status": "received"}, status=status.HTTP_200_OK)
