import json
import logging
import os

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sales.models import Order

from .filters import DarazLocationFilter
from .iop import IopClient, IopRequest
from .models import DarazLocation, DarazSellerStore
from .serializers import DarazLocationImportSerializer, DarazLocationSerializer
from .services.location_service import import_locations_from_csv

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
    using the bundled Lazop Python SDK with signature-based authentication.

    Auth: HMAC-SHA256 signature (sign_method=sha256) — no access_token required.
    Credentials are read exclusively from environment variables:
        DARAZ_APPKEY   – Daraz application key
        DARAZ_SECRET   – Daraz application secret
        DARAZ_API_URL  – (optional) gateway URL, defaults to Daraz Nepal
    """

    permission_classes = [IsAuthenticated]

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
        # 2. Retrieve the order & fetch Daraz seller configuration
        # ------------------------------------------------------------------
        order = get_object_or_404(
            Order.objects.select_related("franchise"), id=order_id
        )

        user = request.user
        user_franchise = getattr(user, "franchise", None)
        if not user_franchise:
            return Response(
                {"error": "Your user account is not associated with any Franchise."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not order.franchise or order.franchise != user_franchise:
            return Response(
                {"error": "You can only send orders belonging to your own franchise."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            store_config = DarazSellerStore.objects.get(franchise=user_franchise)
        except DarazSellerStore.DoesNotExist:
            return Response(
                {
                    "error": f"No Daraz store configuration found for franchise '{user_franchise.name}'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "Preparing to send order %s (ID: %s) to Daraz at %s using signature-only auth",
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

        # dimWeight is required both at top-level AND inside each item (per Daraz reference)
        dim_weight = request.data.get("dimWeight") or {
            "length": str(request.data.get("length", "1")),  # cm
            "width": str(request.data.get("width", "1")),  # cm
            "height": str(request.data.get("height", "1")),  # cm
            "weight": str(request.data.get("weight", "500")),  # grams
        }

        # Pricing map for specific products:
        # Yachu Hair Oil - 2500
        # Hairfall Case Oil - 2500
        # Dandruff Case Oil - 2500
        # Baldness Case Oil - 2500
        # Shampoo Bottle - 1000
        # sachet oil - 990
        # sachet shampoo - 100
        PRICE_MAP = {
            "yachu hair oil": 2500,
            "hairfall case oil": 2500,
            "dandruff case oil": 2500,
            "baldness case oil": 2500,
            "shampoo bottle": 1000,
            "sachet oil": 990,
            "sachet shampoo": 100,
        }

        items_list = []
        for op in order_products:
            product_name = (
                op.product.product.name
                if op.product and op.product.product
                else "Unknown Product"
            )

            # Find item unit price from PRICE_MAP based on substring match or exact match
            name_lower = product_name.lower().strip()
            item_unit_price = None
            for key, val in PRICE_MAP.items():
                if key in name_lower:
                    item_unit_price = val
                    break

            if item_unit_price is None:
                item_unit_price = unit_price

            items_list.append({
                "unitPrice": str(item_unit_price),
                "quantity": str(op.quantity),
                "name": product_name,
                "paidPrice": str(item_unit_price),
                "dimWeight": dim_weight,  # required per Daraz spec
            })

        # ------------------------------------------------------------------
        # 5. Origin / warehouse details (dynamic from store config)
        # ------------------------------------------------------------------
        origin = {
            "name": store_config.origin_name,
            "phone": store_config.origin_phone,
            "email": store_config.origin_email,
            "address": {
                "city": store_config.origin_address_city,
                "id": store_config.origin_address_id,
                "details": store_config.origin_address_details,
                "type": store_config.origin_address_type,
            },
        }

        # ------------------------------------------------------------------
        # 6. Destination / customer details (derived from order)
        # ------------------------------------------------------------------
        location_id = request.data.get("location_id") or request.data.get("location")
        if not location_id:
            return Response(
                {"error": "location_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            daraz_location = DarazLocation.objects.get(id=location_id)
            dest_city = daraz_location.city
            dest_id = daraz_location.l4_id
        except DarazLocation.DoesNotExist:
            return Response(
                {"error": f"DarazLocation with ID {location_id} not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        destination = request.data.get("destination")
        if not destination:
            destination = {
                "address": {
                    "city": dest_city,
                    "details": order.delivery_address or "Delivery address",
                    "id": dest_id,
                },
                "phone": order.phone_number,
                "name": order.full_name,
            }
        else:
            if "address" not in destination:
                destination["address"] = {}
            destination["address"]["city"] = dest_city
            destination["address"]["id"] = dest_id

        # ------------------------------------------------------------------
        # 7. Shipper / seller info (dynamic from store config)
        # ------------------------------------------------------------------
        shipper = {
            "externalSellerId": store_config.shipper_seller_id,
            "platformName": store_config.shipper_platform_name,
            "externalWarehouseCode": store_config.shipper_external_warehouse_code,
            "warehouseName": store_config.shipper_warehouse_name,
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
        options = request.data.get("options")
        if not options:
            options = {
                "deliveryNote": order.remarks or "",
                "partnerOrderId": order.order_code,
                "directReturnToMerchant": "true",
            }
        options["vasFdStorageOption"] = "true"

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
        # dimWeight is a top-level JSON object (NOT inside a 'package' wrapper)
        iop_request.add_api_param("dimWeight", json.dumps(dim_weight))
        iop_request.add_api_param(
            "deliveryOption", request.data.get("deliveryOption", "standard")
        )

        # ------------------------------------------------------------------
        # 10b. Print/log request parameters in a nice format
        # ------------------------------------------------------------------
        pretty_params = {}
        for k, v in iop_request._api_params.items():
            try:
                # Attempt to parse values as JSON so nested objects print nicely
                pretty_params[k] = json.loads(v)
            except (ValueError, TypeError):
                pretty_params[k] = v

        logger.info(
            "Daraz Request Parameters for %s:\n%s",
            order.order_code,
            json.dumps(pretty_params, indent=4, ensure_ascii=False),
        )
        print(
            f"Daraz Request Parameters for {order.order_code}:\n{json.dumps(pretty_params, indent=4, ensure_ascii=False)}"
        )

        try:
            iop_response = client.execute(
                iop_request
            )  # signature-only, no access_token
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

        if success:
            order.logistics = "Daraz"
            order.daraz_location = daraz_location
            update_fields = ["logistics", "daraz_location"]
            tracking_number = response_body.get("data", {}).get("trackingNumber")
            if tracking_number:
                order.tracking_code = tracking_number
                update_fields.append("tracking_code")
                logger.info(
                    "Successfully saved Daraz tracking number %s to order %s",
                    tracking_number,
                    order.order_code,
                )
            package_code = response_body.get("data", {}).get("packageCode")
            if package_code:
                order.package_code = package_code
                update_fields.append("package_code")
                logger.info(
                    "Successfully saved Daraz package code %s to order %s",
                    package_code,
                    order.order_code,
                )
            order.save(update_fields=update_fields)

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


class DarazLocationListView(generics.ListAPIView):
    """
    GET /api/daraz/locations/
    Retrieves the list of Daraz locations. Supports searching by city or area.
    """

    queryset = DarazLocation.objects.all()
    serializer_class = DarazLocationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DarazLocationFilter
    # permission_classes = [IsAuthenticated]


class DarazLocationImportView(APIView):
    """
    POST /api/daraz/locations/import/
    Imports Daraz locations from a CSV file.
    """

    # permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = DarazLocationImportSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file_obj = serializer.validated_data["file"]
        try:
            count = import_locations_from_csv(file_obj)
            return Response(
                {"message": "Locations imported successfully.", "count": count},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to import CSV: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CancelDarazOrderView(APIView):
    """
    POST /api/daraz/orders/<order_id>/cancel/
    Cancels a package/order on Daraz.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related("franchise"), id=order_id
        )

        user = request.user
        user_franchise = getattr(user, "franchise", None)
        if not user_franchise:
            return Response(
                {"error": "Your user account is not associated with any Franchise."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not order.franchise or order.franchise != user_franchise:
            return Response(
                {
                    "error": "You can only cancel orders belonging to your own franchise."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        package_code = order.package_code
        if not package_code:
            return Response(
                {"error": "Package code is required to cancel this order on Daraz."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get("reason") or "User trigger cancel"

        try:
            client = _get_client()
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        iop_request = IopRequest("/logistics/epis/packages/cancel", "POST")
        iop_request.add_api_param("packageCode", str(package_code))
        iop_request.add_api_param("reason", str(reason))

        # Print and log API payload
        pretty_params = {}
        for k, v in iop_request._api_params.items():
            try:
                pretty_params[k] = json.loads(v)
            except (ValueError, TypeError):
                pretty_params[k] = v

        logger.info(
            "Daraz Cancel Request Parameters for %s:\n%s",
            order.order_code,
            json.dumps(pretty_params, indent=4, ensure_ascii=False),
        )
        print(
            f"Daraz Cancel Request Parameters for {order.order_code}:\n{json.dumps(pretty_params, indent=4, ensure_ascii=False)}"
        )

        logger.info(
            "Sending cancel request to Daraz for package %s, reason: %s",
            package_code,
            reason,
        )

        try:
            iop_response = client.execute(iop_request)
        except Exception as exc:
            logger.exception(
                "Daraz cancel SDK request failed for order %s", order.order_code
            )
            return Response(
                {"error": "Failed to reach Daraz API.", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        response_body = iop_response.body if isinstance(iop_response.body, dict) else {}

        # Print and log API response
        logger.info(
            "Daraz Cancel Response for order %s:\n%s",
            order.order_code,
            json.dumps(response_body, indent=4, ensure_ascii=False),
        )
        print(
            f"Daraz Cancel Response for order {order.order_code}:\n{json.dumps(response_body, indent=4, ensure_ascii=False)}"
        )

        daraz_code = str(iop_response.code) if iop_response.code is not None else ""
        success = daraz_code == "0"

        if success:
            order.order_status = "Cancelled"
            order.save(update_fields=["order_status"])

        http_status = status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST

        return Response(
            {
                "success": success,
                "daraz_code": iop_response.code,
                "daraz_message": iop_response.message,
                "daraz_request_id": iop_response.request_id,
                "body": response_body,
            },
            status=http_status,
        )


class CancelDarazOrderByPackageCodeView(APIView):
    """
    POST /api/daraz/orders/cancel/
    Cancels a Daraz package directly using a packageCode provided in the request body.
    Does not require an internal order record.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        package_code = request.data.get("package_code")
        if not package_code:
            return Response(
                {"error": "package_code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get("reason") or "User trigger cancel"

        try:
            client = _get_client()
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        iop_request = IopRequest("/logistics/epis/packages/cancel", "POST")
        iop_request.add_api_param("packageCode", str(package_code))
        iop_request.add_api_param("reason", str(reason))

        # Log API payload
        pretty_params = {}
        for k, v in iop_request._api_params.items():
            try:
                pretty_params[k] = json.loads(v)
            except (ValueError, TypeError):
                pretty_params[k] = v

        logger.info(
            "Daraz Cancel Request Parameters for package %s:\n%s",
            package_code,
            json.dumps(pretty_params, indent=4, ensure_ascii=False),
        )
        print(
            f"Daraz Cancel Request Parameters for package {package_code}:\n"
            f"{json.dumps(pretty_params, indent=4, ensure_ascii=False)}"
        )

        logger.info(
            "Sending cancel request to Daraz for package %s, reason: %s",
            package_code,
            reason,
        )

        try:
            iop_response = client.execute(iop_request)
        except Exception as exc:
            logger.exception(
                "Daraz cancel SDK request failed for package %s", package_code
            )
            return Response(
                {"error": "Failed to reach Daraz API.", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        response_body = iop_response.body if isinstance(iop_response.body, dict) else {}

        # Log API response
        logger.info(
            "Daraz Cancel Response for package %s:\n%s",
            package_code,
            json.dumps(response_body, indent=4, ensure_ascii=False),
        )
        print(
            f"Daraz Cancel Response for package {package_code}:\n"
            f"{json.dumps(response_body, indent=4, ensure_ascii=False)}"
        )

        daraz_code = str(iop_response.code) if iop_response.code is not None else ""
        success = daraz_code == "0"

        http_status = status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST

        return Response(
            {
                "success": success,
                "daraz_code": iop_response.code,
                "daraz_message": iop_response.message,
                "daraz_request_id": iop_response.request_id,
                "body": response_body,
            },
            status=http_status,
        )
