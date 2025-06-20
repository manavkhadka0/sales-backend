import os
from rest_framework.views import APIView
from rest_framework.response import Response
from sales.models import Order, OrderProduct
import requests
from .models import Dash
from .serializers import DashLoginSerializer, DashSerializer
from rest_framework import status
from datetime import timedelta
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListCreateAPIView
from dotenv import load_dotenv

load_dotenv()

# Reusable function for Dash login
DASH_BASE_URL = os.getenv('DASH_BASE_URL')


class DashListCreateView(ListCreateAPIView):
    queryset = Dash.objects.all()
    serializer_class = DashSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user = request.user
        if not hasattr(user, 'franchise') or not user.franchise:
            return Response({"error": "User does not have a franchise."}, status=400)

        # Attach user and franchise to the data
        data = request.data.copy()
        data['franchise'] = user.franchise.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


def dash_login(email, password, dash_obj=None):
    # Use values from dash_obj if provided, else use defaults
    client_id = dash_obj.client_id
    client_secret = dash_obj.client_secret
    grant_type = dash_obj.grant_type
    DASH_LOGIN_URL = f"{DASH_BASE_URL}/api/v1/login/client/"
    body = {
        "clientId": client_id,
        "clientSecret": client_secret,
        "grantType": grant_type,
        "email": email,
        "password": password
    }
    try:
        response = requests.post(DASH_LOGIN_URL, json=body)
        if response.status_code == 200:
            data = response.json().get("data", {})
            access_token = data.get("accessToken")
            refresh_token = data.get("refreshToken")
            expires_in = data.get("expiresIn")
            expires_at = timezone.now() + timedelta(seconds=expires_in) if expires_in else None
            dash_defaults = {
                "password": password,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": grant_type,
            }
            dash_obj_db, created = Dash.objects.update_or_create(
                email=email,
                defaults=dash_defaults
            )
            return dash_obj_db, None
        elif response.status_code == 422:
            return None, response.json()
        else:
            return None, {"error": "Failed to login to Dash", "details": response.text, "status": response.status_code}
    except requests.RequestException as e:
        return None, {"error": "Failed to login to Dash", "details": str(e)}


class DashLoginView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DashLoginSerializer

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        if not email or not password:
            return Response({"error": "Email and password are required."}, status=400)
        user = request.user if request.user.is_authenticated else None
        dash = Dash.objects.get(franchise=user.franchise)
        dash_obj, error = dash_login(email, password, dash_obj=dash)
        if dash_obj:
            serializer = DashSerializer(dash_obj)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            status_code = error.get("status", 400)
            return Response(error, status=status_code)


class SendOrderToDashByIdView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        user = request.user
        if not hasattr(user, 'franchise') or not user.franchise:
            return Response({"error": "User does not have a franchise."}, status=400)
        try:
            dash_obj = Dash.objects.get(franchise=user.franchise)
        except Dash.DoesNotExist:
            return Response({"error": "Dash credentials not found."}, status=404)

        # Check if token is missing or expired
        if not dash_obj.access_token or (dash_obj.expires_at and dash_obj.expires_at <= timezone.now()):
            dash_obj, error = dash_login(
                dash_obj.email, dash_obj.password, dash_obj=dash_obj)
            if not dash_obj:
                status_code = error.get("status", 400)
                return Response({"error": "Failed to refresh Dash token", **error}, status=status_code)

        access_token = dash_obj.access_token

        DASH_API_URL = f"{DASH_BASE_URL}/api/v1/clientOrder/add-order"
        HEADERS = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": f"Order with id {order_id} does not exist."}, status=404)

        if order.order_status != "Processing":
            return Response({"error": "Order is not in Processing status."}, status=400)

        order_products = OrderProduct.objects.filter(order=order)
        product_name = ", ".join(
            [f"{op.quantity}-{op.product.product.name}" for op in order_products]
        )

        product_price = order.total_amount
        if order.prepaid_amount:
            product_price = order.total_amount - order.prepaid_amount

        payment_type = "pre-paid" if order.prepaid_amount and (
            order.total_amount - order.prepaid_amount) == 0 else "cashOnDelivery"

        customer = {
            "receiver_name": order.full_name,
            "receiver_contact": order.phone_number,
            "receiver_alternate_number": order.alternate_phone_number or "",
            "receiver_address": order.delivery_address,
            "receiver_location": order.dash_location.name if order.dash_location else "",
            "payment_type": payment_type,
            "product_name": product_name,
            "client_note": order.remarks or "",
            "receiver_landmark": order.landmark or "",
            "order_reference_id": str(order.id),
            "product_price": float(product_price),
        }

        payload = {"customers": [customer]}
        try:
            dash_response = requests.post(
                DASH_API_URL, json=payload, headers=HEADERS, timeout=30)
            dash_response.raise_for_status()

            # Parse the response to get tracking codes
            response_data = dash_response.json()
            tracking_codes = []
            if response_data.get('data', {}).get('detail'):
                tracking_codes = [
                    {
                        'tracking_code': item.get('tracking_code'),
                        'order_reference_id': item.get('order_reference_id')
                    }
                    for item in response_data['data']['detail']
                ]

            order.order_status = "Sent to Dash"
            order.save()

            return Response({
                "message": "Order sent to Dash successfully.",
                "tracking_codes": tracking_codes,
                "dash_response": response_data
            }, status=200)
        except requests.RequestException as e:
            return Response({
                "error": "Failed to send order to Dash.",
                "details": str(e)
            }, status=500)
