# sales/views.py
import os

import requests
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from pickndrop.models import PickNDrop
from pickndrop.serializers import PickNDropSerializer
from pickndrop.utils import create_pickndrop_order
from sales.models import Inventory, Location, Order, OrderProduct


class PickNDropListCreateView(ListCreateAPIView):
    serializer_class = PickNDropSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PickNDrop.objects.filter(franchise=self.request.user.franchise)

    def create(self, request, *args, **kwargs):
        user = request.user
        if not hasattr(user, "franchise") or not user.franchise:
            return Response({"error": "User does not have a franchise."}, status=400)

        # Attach user and franchise to the data
        data = request.data.copy()
        data["franchise"] = user.franchise.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class FetchAndSavePicknDropBranches(APIView):
    """
    Fetch branches from Pick n Drop API and save to Location model
    """

    def get(self, request):
        base_url = os.getenv("PICKNDROP_BASE_URL")  # replace with your baseUrl
        endpoint = f"{base_url}/api/method/logi360.api.get_branches"
        # Your API key and secret
        api_key = os.getenv("PICKNDROP_CLIENT_KEY")
        api_secret = os.getenv("PICKNDROP_CLIENT_SECRET")

        headers = {
            "Authorization": f"token {api_key}:{api_secret}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(endpoint, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("message", {}).get("status") != "success":
                return Response(
                    {"error": "Failed to fetch branches"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            branches = data["message"]["data"]["branches"]
            saved_locations = []

            for branch in branches:
                location, created = Location.objects.update_or_create(
                    name=branch["branch_name"],
                    logistics="PicknDrop",
                    defaults={"coverage_areas": branch.get("area", [])},
                )
                saved_locations.append(location.name)

            return Response(
                {
                    "status": "success",
                    "saved_locations_count": len(saved_locations),
                }
            )

        except requests.RequestException as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SendOrderToPicknDropByIdView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        user = request.user

        if not hasattr(user, "franchise") or not user.franchise:
            return Response({"error": "User does not have a franchise."}, status=400)

        try:
            order = Order.objects.get(id=order_id)
            pickndrop_obj = PickNDrop.objects.get(franchise=user.franchise)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=404)
        except PickNDrop.DoesNotExist:
            return Response({"error": "PickNDrop credentials not found."}, status=404)

        result = create_pickndrop_order(order, pickndrop_obj)

        # Frappe Authentication error
        if "exception" in result:
            return Response(
                {
                    "status": "error",
                    "message": "PickNDrop authentication failed",
                    "details": result,
                },
                status=400,
            )

        # Network error
        if "error" in result:
            return Response(
                {"status": "error", "message": result["error"]},
                status=400,
            )

        # ---------------------------------------------------------
        # 🚨 CRITICAL FIX — HANDLE PickNDrop business logic errors
        # ---------------------------------------------------------
        # structure:
        # { "message": { "status": "error", "message": "..."} }
        # ---------------------------------------------------------
        if isinstance(result, dict):
            # Explicit error payload from helper
            if result.get("status") == "error":
                return Response(
                    {
                        "status": "error",
                        "message": result.get(
                            "message", "PickNDrop rejected the order"
                        ),
                        "error_code": result.get("error_code"),
                        "details": result.get("response", result),
                    },
                    status=400,
                )

            inner = result.get("message")
            if isinstance(inner, dict) and inner.get("status") == "error":
                return Response(
                    {
                        "status": "error",
                        "message": inner.get("message", "PickNDrop rejected the order"),
                        "error_code": inner.get("error_code"),
                        "details": inner,
                    },
                    status=400,
                )

        # SUCCESS
        if isinstance(result, dict) and result.get("status") == "success":
            return Response(
                {
                    "status": "success",
                    "message": "Order sent to PicknDrop successfully.",
                    "data": result,
                },
                status=200,
            )

        return Response(
            {
                "status": "error",
                "message": "PickNDrop returned an unexpected response.",
                "details": result,
            },
            status=400,
        )


# Mapping table
PICKNDROP_STATUS_MAP = {
    "package_pickup_assigned": "Sent to PicknDrop",
    "package_received_at_hub": "Verified",
    "ready_for_dispatched_last_mile_hero": "Out For Delivery",
    "out_for_delivery": "Out For Delivery",
    "about_to_deliver": "Out For Delivery",
    "1st_attempt_failed": "Rescheduled",
    "package_redelivery": "Rescheduled",
    "delivered": "Delivered",
    "delivery_failed_and_cancelled": "Cancelled",
    "return_at_transit_hub": "Return Pending",
    "received_from_transporter_to_dispatched_hub": "Return Pending",
    "package_returned": "Returned By PicknDrop",
    "Cancelled": "Cancelled",
}


class PickNDropWebhookView(APIView):
    """
    Receive PickNDrop webhook and update Order status.
    """

    permission_classes = [AllowAny]  # Webhook is public

    def post(self, request):
        payload = request.data

        tracking_number = payload.get("order_id")
        status = payload.get("status")
        comments = payload.get("comments", "")

        if not tracking_number or not status:
            return Response({"error": "Invalid payload"}, status=400)

        # Find order
        try:
            order = Order.objects.get(tracking_code=tracking_number)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found for tracking number"},
                status=404,
            )

        # Store previous status for comparison
        previous_status = order.order_status

        # Map PicknDrop → Internal Status
        mapped_status = PICKNDROP_STATUS_MAP.get(status)

        if not mapped_status:
            order.remarks = f"[WEBHOOK UNKNOWN STATUS] {status}: {comments}"
            order.save(update_fields=["remarks"])
            return Response(
                {
                    "status": "ignored",
                    "message": f"Unknown status received: {status}",
                },
                status=200,
            )

        # ------------------------------
        # UPDATE ORDER STATUS FROM WEBHOOK
        # ------------------------------
        order.order_status = mapped_status

        # Append webhook comments
        if comments:
            existing = order.remarks or ""
            order.remarks = f"{existing}\nWebhook: {comments}"

        order.save(update_fields=["order_status", "remarks"])

        # -----------------------------------------
        # 6️⃣ HANDLE ORDER CANCELLATION / RETURNS
        # -----------------------------------------

        CANCEL_RETURN_STATUSES = [
            "Cancelled",
            "Returned By Customer",
            "Returned By Dash",
            "Returned By YDM",
            "Returned By PicknDrop",
        ]

        if (
            mapped_status in CANCEL_RETURN_STATUSES
            and previous_status != mapped_status  # Prevent double-restock
        ):
            order_products = OrderProduct.objects.filter(order=order).select_related(
                "product__product"
            )

            for order_product in order_products:
                try:
                    inventory = Inventory.objects.get(
                        product__id=order_product.product.product.id,
                        franchise=order.franchise,
                    )

                    inventory.quantity += order_product.quantity
                    inventory.save()
                except Inventory.DoesNotExist:
                    return Response(
                        {
                            "detail": f"Inventory not found for product {order_product.product.product.name}"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        return Response(
            {
                "status": "success",
                "tracking_number": tracking_number,
                "new_status": mapped_status,
            },
            status=200,
        )
