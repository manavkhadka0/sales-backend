import datetime
import json
import logging
import os

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sales.models import Order

from .iop import IopClient, IopRequest
from .models import DarazSellerStore

logger = logging.getLogger(__name__)

# Daraz Nepal REST gateway
DARAZ_API_URL = os.getenv("DARAZ_API_URL", "https://api.daraz.com.np/rest")


def _get_client() -> IopClient:
    """Return an IopClient initialised from environment variables."""
    app_key = os.getenv("DARAZ_APPKEY", "")
    app_secret = os.getenv("DARAZ_SECRET", "")

    if not app_key or not app_secret:
        raise ValueError(
            "DARAZ_APPKEY and DARAZ_SECRET must be set in the environment."
        )

    return IopClient(DARAZ_API_URL, app_key, app_secret)


class SendOrderToDarazView(APIView):
    """
    POST /daraz/orders/<order_id>/send/

    Sends a sales order to the Daraz Open Platform EPIS Packages endpoint
    using the bundled Lazop Python SDK.

    Credentials are read exclusively from environment variables:
        DARAZ_APPKEY   – Daraz application key
        DARAZ_SECRET   – Daraz application secret
        DARAZ_API_URL  – (optional) gateway URL, defaults to Daraz Nepal

    An optional `access_token` may be supplied in the request body when
    acting on behalf of a seller via OAuth.
    """

    def post(self, request, order_id):
        # ------------------------------------------------------------------
        # 1. Build the SDK client from env credentials
        # ------------------------------------------------------------------
        try:
            client = _get_client()
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ------------------------------------------------------------------
        # 2. Retrieve the order
        # ------------------------------------------------------------------
        order = get_object_or_404(Order, id=order_id)

        # ------------------------------------------------------------------
        # 3. Retrieve the access token (check body -> DB store -> Env)
        # ------------------------------------------------------------------
        access_token = request.data.get("access_token")
        if not access_token and order.franchise:
            store_record = DarazSellerStore.objects.filter(
                franchise=order.franchise
            ).first()
            if store_record:
                access_token = store_record.access_token
                logger.info(
                    "Retrieved active Daraz Access Token from database for franchise: %s",
                    order.franchise.name,
                )

        if not access_token:
            access_token = os.getenv("DARAZ_ACCESS_TOKEN", "") or None

        if not access_token:
            return Response(
                {
                    "error": "This Franchise has not authorized their Daraz Seller account yet. Please connect the store first."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "Preparing to send order %s (ID: %s) to Daraz at %s",
            order.order_code,
            order.id,
            DARAZ_API_URL,
        )

        # ------------------------------------------------------------------
        # 3. Build the IopRequest
        # ------------------------------------------------------------------
        iop_request = IopRequest("/logistics/epis/packages", "POST")

        # ------------------------------------------------------------------
        # 4. Items from order products
        # ------------------------------------------------------------------
        order_products = order.order_products.all()

        if not order_products.exists():
            return Response(
                {"error": "This order has no associated products."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_qty = sum(op.quantity for op in order_products) or 1
        subtotal = order.total_amount - (order.delivery_charge or 0)
        unit_price = max(int(subtotal / total_qty), 0)

        items_list = []
        for op in order_products:
            product_name = (
                op.product.product.name
                if op.product and op.product.product
                else "Unknown Product"
            )
            items_list.append({
                "unitPrice": str(unit_price),
                "quantity": str(op.quantity),
                "name": product_name,
                "paidPrice": str(unit_price),
            })

        # ------------------------------------------------------------------
        # 5. Origin / warehouse details  (configurable via env)
        # ------------------------------------------------------------------
        origin = request.data.get("origin") or {
            "address": {
                "city": os.getenv("DARAZ_ORIGIN_CITY", "Kathmandu"),
                "details": os.getenv("DARAZ_ORIGIN_DETAILS", "Kathmandu, Nepal"),
                "id": os.getenv("DARAZ_ORIGIN_ID", "R80199317"),
            },
            "phone": os.getenv("DARAZ_ORIGIN_PHONE", "9800000000"),
            "name": os.getenv("DARAZ_ORIGIN_NAME", "Baliyo Warehouse"),
            "email": os.getenv("DARAZ_ORIGIN_EMAIL", "warehouse@baliyo.com"),
        }

        # ------------------------------------------------------------------
        # 6. Destination / customer details (derived from order)
        # ------------------------------------------------------------------
        destination = request.data.get("destination") or {
            "address": {
                "city": order.city or "Kathmandu",
                "details": order.delivery_address or "Delivery address",
            },
            "phone": order.phone_number,
            "name": order.full_name,
        }

        # ------------------------------------------------------------------
        # 7. Shipper / seller info
        # ------------------------------------------------------------------
        shipper = request.data.get("shipper") or {
            "externalSellerId": os.getenv("DARAZ_SELLER_ID", "L001231321"),
            "platformName": os.getenv("DARAZ_PLATFORM_NAME", "Baliyo"),
            "warehouseName": os.getenv("DARAZ_WAREHOUSE_NAME", "Main Warehouse"),
            "externalWarehouseCode": os.getenv("DARAZ_WAREHOUSE_CODE", "WH_0001"),
        }

        # ------------------------------------------------------------------
        # 8. Payment info
        # ------------------------------------------------------------------
        payment_type = (
            "COD" if order.payment_method == "Cash on Delivery" else "NON-COD"
        )
        payment = request.data.get("payment") or {
            "totalAmount": str(order.total_amount),
            "currency": os.getenv("DARAZ_CURRENCY", "NPR"),
            "paymentType": payment_type,
        }

        # ------------------------------------------------------------------
        # 9. Delivery options
        # ------------------------------------------------------------------
        options = request.data.get("options") or {
            "deliveryNote": order.remarks or "",
            "partnerOrderId": order.order_code,
            "directReturnToMerchant": "true",
        }

        # ------------------------------------------------------------------
        # 10. Populate API parameters on the request object
        # ------------------------------------------------------------------
        creation_time = (
            int(order.created_at.timestamp() * 1000)
            if order.created_at
            else int(timezone.now().timestamp() * 1000)
        )

        iop_request.add_api_param("externalOrderId", order.order_code)
        iop_request.add_api_param("platformOrderCreationTime", str(creation_time))
        iop_request.add_api_param(
            "dangerousGood", request.data.get("dangerousGood", "false")
        )
        iop_request.add_api_param("items", json.dumps(items_list))
        iop_request.add_api_param("shipper", json.dumps(shipper))
        iop_request.add_api_param("origin", json.dumps(origin))
        iop_request.add_api_param("destination", json.dumps(destination))
        iop_request.add_api_param("payment", json.dumps(payment))
        iop_request.add_api_param("options", json.dumps(options))
        iop_request.add_api_param(
            "deliveryOption", request.data.get("deliveryOption", "standard")
        )

        # ------------------------------------------------------------------
        # 11. Execute the request via the Lazop SDK
        # ------------------------------------------------------------------
        logger.info(
            "Executing Daraz EPIS package request for order %s", order.order_code
        )

        try:
            iop_response = client.execute(iop_request, access_token)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Daraz SDK request failed for order %s", order.order_code)
            return Response(
                {"error": "Failed to reach Daraz API.", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ------------------------------------------------------------------
        # 12. Parse and return the response
        # ------------------------------------------------------------------
        response_body = iop_response.body if isinstance(iop_response.body, dict) else {}

        # The Lazop SDK sets code="0" on success
        daraz_code = str(iop_response.code) if iop_response.code is not None else ""
        success = daraz_code == "0"

        log_fn = logger.info if success else logger.warning
        log_fn(
            "Daraz response for order %s — code=%s message=%s request_id=%s",
            order.order_code,
            iop_response.code,
            iop_response.message,
            iop_response.request_id,
        )

        http_status = status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST

        return Response(
            {
                "success": success,
                "daraz_code": iop_response.code,
                "daraz_type": iop_response.type,
                "daraz_message": iop_response.message,
                "daraz_request_id": iop_response.request_id,
                "order_code": order.order_code,
                "body": response_body,
            },
            status=http_status,
        )


class SaveDarazTokenView(APIView):
    """
    POST /api/daraz/save-token/
    Exchanges the authorization code from the frontend for seller tokens and saves them.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response(
                {"error": "Authorization code not provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if not user.franchise:
            return Response(
                {"error": "Your account is not associated with any Franchise."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        franchise = user.franchise

        # Request tokens using global Daraz auth REST gateway
        app_key = os.getenv("DARAZ_APPKEY", "")
        app_secret = os.getenv("DARAZ_SECRET", "")
        if not app_key or not app_secret:
            return Response(
                {
                    "error": "DARAZ_APPKEY and DARAZ_SECRET must be set in the environment."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        client = IopClient("https://api.daraz.com.np/rest", app_key, app_secret)

        iop_request = IopRequest("/auth/token/create", "POST")
        iop_request.add_api_param("code", code)

        try:
            iop_response = client.execute(iop_request)
            response_data = (
                iop_response.body if isinstance(iop_response.body, dict) else {}
            )

            if "access_token" not in response_data:
                return Response(
                    {
                        "error": "Failed to retrieve access token.",
                        "details": response_data,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            access_token = response_data.get("access_token")
            refresh_token = response_data.get("refresh_token")
            expires_in = int(response_data.get("expires_in", 2592000))
            refresh_expires_in = int(response_data.get("refresh_expires_in", 31536000))

            now = timezone.now()
            access_expiry = now + datetime.timedelta(seconds=expires_in)
            refresh_expiry = now + datetime.timedelta(seconds=refresh_expires_in)

            # Map the tokens to the specific Franchise model instance
            store_record, created = DarazSellerStore.objects.update_or_create(
                franchise=franchise,
                defaults={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "access_token_expires_at": access_expiry,
                    "refresh_token_expires_at": refresh_expiry,
                },
            )

            return Response(
                {
                    "success": True,
                    "message": "Successfully linked your Franchise store to Daraz!",
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": "Internal error processing tokens.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GetDarazConfigView(APIView):
    """
    GET /api/daraz/config/
    Retrieves the public configuration parameters (App Key) and connection status.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.franchise:
            return Response(
                {"error": "Your account is not associated with any Franchise."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connected = DarazSellerStore.objects.filter(franchise=user.franchise).exists()
        app_key = os.getenv("DARAZ_APPKEY", "")

        return Response(
            {
                "app_key": app_key,
                "connected": connected,
            },
            status=status.HTTP_200_OK,
        )
