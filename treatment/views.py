import json

from django.db import models
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sales.views import CustomPagination

from .filters import CustomerTreatmentFilter, ImageFilter, PaymentHistoryFilter
from .models import CustomerTreatment, Image, PaymentHistory
from .serializers import (
    CustomerTreatmentSerializer,
    ImageSerializer,
    PaymentHistorySerializer,
)


def parse_json_field(data, field_name):
    """Helper function to parse JSON data from request form-data/JSON payload"""
    val = data.get(field_name)
    if isinstance(val, (list, dict)):
        return val
    elif isinstance(val, str) and val.strip():
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format for {field_name}")
    return None


class CustomerTreatmentListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomerTreatmentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )
    filterset_class = CustomerTreatmentFilter
    pagination_class = CustomPagination
    search_fields = ["name", "phone_number"]
    ordering_fields = ["created_at", "name", "treatment_type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = (
            CustomerTreatment.objects
            .select_related("service_by", "franchise")
            .prefetch_related("images", "payment_history")
            .all()
        )

        if not user or not user.is_authenticated:
            return CustomerTreatment.objects.none()

        user_role = getattr(user, "role", None)

        if user_role == "Franchise":
            return qs.filter(franchise=user.franchise)
        elif user_role == "Treatment Staff":
            if hasattr(user, "franchise") and user.franchise:
                return qs.filter(
                    models.Q(franchise=user.franchise)
                    | models.Q(franchise__isnull=True)
                )
            return qs.all()
        elif user_role == "SuperAdmin":
            return qs.all()
        elif hasattr(user, "franchise") and user.franchise:
            return qs.filter(franchise=user.franchise)

        return qs.all()

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        images_data = parse_json_field(request.data, "images_data")

        # Automatically link franchise from token if not explicitly provided
        if (
            not data.get("franchise")
            and request.user
            and request.user.is_authenticated
            and hasattr(request.user, "franchise")
            and request.user.franchise
        ):
            data["franchise"] = request.user.franchise.id

        # Automatically link user from token if service_by ID is not specified
        if (
            not data.get("service_by")
            and request.user
            and request.user.is_authenticated
        ):
            data["service_by"] = request.user.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save(images_data=images_data)

        headers = self.get_success_headers(serializer.data)
        return Response(
            self.get_serializer(customer).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


class CustomerTreatmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerTreatmentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        user = self.request.user
        qs = (
            CustomerTreatment.objects
            .select_related("service_by", "franchise")
            .prefetch_related("images", "payment_history")
            .all()
        )

        if not user or not user.is_authenticated:
            return CustomerTreatment.objects.none()

        user_role = getattr(user, "role", None)

        if user_role == "Franchise":
            return qs.filter(franchise=user.franchise)
        elif user_role == "Treatment Staff":
            if hasattr(user, "franchise") and user.franchise:
                return qs.filter(
                    models.Q(franchise=user.franchise)
                    | models.Q(franchise__isnull=True)
                )
            return qs.all()
        elif user_role == "SuperAdmin":
            return qs.all()
        elif hasattr(user, "franchise") and user.franchise:
            return qs.filter(franchise=user.franchise)

        return qs.all()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        data = request.data.copy()

        images_data = parse_json_field(request.data, "images_data")
        delete_image_ids = parse_json_field(request.data, "delete_images")

        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save(
            images_data=images_data, delete_image_ids=delete_image_ids
        )

        return Response(self.get_serializer(customer).data)


class ImageListCreateView(generics.ListCreateAPIView):
    queryset = Image.objects.select_related("customer_treatment").all()
    serializer_class = ImageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = ImageFilter
    ordering_fields = ["day_number", "created_at"]
    ordering = ["day_number", "created_at"]


class ImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Image.objects.select_related("customer_treatment").all()
    serializer_class = ImageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)


class PaymentHistoryListCreateView(generics.ListCreateAPIView):
    queryset = PaymentHistory.objects.select_related(
        "customer_treatment", "created_by"
    ).all()
    serializer_class = PaymentHistorySerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = PaymentHistoryFilter
    ordering_fields = ["payment_date", "amount"]
    ordering = ["-payment_date"]

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        if not serializer.validated_data.get("created_by") and user:
            serializer.save(created_by=user)
        else:
            serializer.save()


class PaymentHistoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PaymentHistory.objects.select_related(
        "customer_treatment", "created_by"
    ).all()
    serializer_class = PaymentHistorySerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
