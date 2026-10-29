from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from offlineSales.models import (
    OfflineCustomer,
    OfflineOrder,
    OfflineOrderItem,
    OfflinePaymentHistory,
)
from offlineSales.services.order_service import (
    create_offline_order,
    update_offline_order,
)
from offlineSales.services.payment_service import record_order_payment


class OfflineCustomerSerializer(serializers.ModelSerializer):
    franchise_name = serializers.CharField(source="franchise.name", read_only=True)
    sales_person_name = serializers.CharField(
        source="sales_person.first_name", read_only=True
    )
    total_orders_count = serializers.SerializerMethodField()
    total_purchased_amount = serializers.SerializerMethodField()
    total_paid_amount = serializers.SerializerMethodField()
    total_remaining_amount = serializers.SerializerMethodField()

    class Meta:
        model = OfflineCustomer
        fields = [
            "id",
            "store_name",
            "contact_person",
            "phone_number",
            "address",
            "franchise",
            "franchise_name",
            "sales_person",
            "sales_person_name",
            "is_active",
            "created_at",
            "updated_at",
            "total_orders_count",
            "total_purchased_amount",
            "total_paid_amount",
            "total_remaining_amount",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "franchise_name",
            "sales_person_name",
            "total_orders_count",
            "total_purchased_amount",
            "total_paid_amount",
            "total_remaining_amount",
        ]

    def get_total_orders_count(self, obj) -> int:
        annotated = getattr(obj, "annotated_total_orders", None)
        return annotated if annotated is not None else obj.total_orders_count

    def get_total_purchased_amount(self, obj) -> Decimal:
        annotated = getattr(obj, "annotated_total_purchased", None)
        return annotated if annotated is not None else obj.total_purchased_amount

    def get_total_paid_amount(self, obj) -> Decimal:
        annotated = getattr(obj, "annotated_total_paid", None)
        return annotated if annotated is not None else obj.total_paid_amount

    def get_total_remaining_amount(self, obj) -> Decimal:
        annotated = getattr(obj, "annotated_total_remaining", None)
        return annotated if annotated is not None else obj.total_remaining_amount

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if (
            not attrs.get("franchise")
            and user
            and hasattr(user, "franchise")
            and user.franchise
        ):
            attrs["franchise"] = user.franchise

        if not attrs.get("sales_person") and user and user.is_authenticated:
            attrs["sales_person"] = user

        if not attrs.get("franchise"):
            raise serializers.ValidationError({"franchise": "Franchise is required."})

        return attrs


class OfflineOrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="inventory.product.id", read_only=True)
    product_name = serializers.CharField(
        source="inventory.product.name", read_only=True
    )
    product_image = serializers.FileField(
        source="inventory.product.image", read_only=True
    )

    class Meta:
        model = OfflineOrderItem
        fields = [
            "id",
            "inventory",
            "product_id",
            "product_name",
            "product_image",
            "quantity",
        ]
        read_only_fields = ["id"]


class OfflinePaymentHistorySerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(read_only=True)
    customer_id = serializers.IntegerField(source="customer.id", read_only=True)
    order_code = serializers.SerializerMethodField()
    customer_store_name = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    recorded_by_name = serializers.CharField(
        source="recorded_by.first_name", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )

    class Meta:
        model = OfflinePaymentHistory
        fields = [
            "id",
            "customer",
            "customer_id",
            "order",
            "order_code",
            "customer_store_name",
            "customer_phone",
            "amount",
            "payment_method",
            "payment_method_display",
            "payment_date",
            "payment_screenshot",
            "remarks",
            "recorded_by",
            "recorded_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "customer",
            "customer_id",
            "order_code",
            "customer_store_name",
            "customer_phone",
            "recorded_by_name",
            "payment_method_display",
            "created_at",
            "updated_at",
        ]

    def get_order_code(self, obj) -> str | None:
        return obj.order.order_code if obj.order else None

    def get_customer_store_name(self, obj) -> str:
        if obj.customer:
            return obj.customer.store_name
        if obj.order and obj.order.customer:
            return obj.order.customer.store_name
        return ""

    def get_customer_phone(self, obj) -> str:
        if obj.customer:
            return obj.customer.phone_number
        if obj.order and obj.order.customer:
            return obj.order.customer.phone_number
        return ""


class OfflineOrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.store_name", read_only=True)
    customer_contact_person = serializers.CharField(
        source="customer.contact_person", read_only=True
    )
    customer_phone = serializers.CharField(
        source="customer.phone_number", read_only=True
    )
    franchise_name = serializers.CharField(source="franchise.name", read_only=True)
    sales_person_name = serializers.CharField(
        source="sales_person.first_name", read_only=True
    )
    items_count = serializers.SerializerMethodField()
    items = OfflineOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = OfflineOrder
        fields = [
            "id",
            "order_code",
            "customer",
            "customer_name",
            "customer_contact_person",
            "customer_phone",
            "franchise",
            "franchise_name",
            "sales_person",
            "sales_person_name",
            "order_date",
            "order_status",
            "payment_status",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "items_count",
            "remarks",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_items_count(self, obj) -> int:
        if (
            hasattr(obj, "_prefetched_objects_cache")
            and "items" in obj._prefetched_objects_cache
        ):
            return len(obj.items.all())
        return obj.items.count()


class OfflineOrderDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.store_name", read_only=True)
    customer_contact_person = serializers.CharField(
        source="customer.contact_person", read_only=True
    )
    customer_phone = serializers.CharField(
        source="customer.phone_number", read_only=True
    )
    franchise_name = serializers.CharField(source="franchise.name", read_only=True)
    sales_person_name = serializers.CharField(
        source="sales_person.first_name", read_only=True
    )
    items_count = serializers.SerializerMethodField()
    items = OfflineOrderItemSerializer(many=True, read_only=True)
    payment_history = OfflinePaymentHistorySerializer(many=True, read_only=True)

    class Meta:
        model = OfflineOrder
        fields = [
            "id",
            "order_code",
            "customer",
            "customer_name",
            "customer_contact_person",
            "customer_phone",
            "franchise",
            "franchise_name",
            "sales_person",
            "sales_person_name",
            "order_date",
            "order_status",
            "payment_status",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "items_count",
            "remarks",
            "items",
            "payment_history",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "order_code",
            "customer",
            "customer_name",
            "customer_contact_person",
            "customer_phone",
            "franchise",
            "franchise_name",
            "sales_person",
            "sales_person_name",
            "payment_status",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "items_count",
            "items",
            "payment_history",
            "created_at",
            "updated_at",
        ]

    def get_items_count(self, obj) -> int:
        if (
            hasattr(obj, "_prefetched_objects_cache")
            and "items" in obj._prefetched_objects_cache
        ):
            return len(obj.items.all())
        return obj.items.count()

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return update_offline_order(instance, validated_data, user)


class OfflineOrderItemCreateSerializer(serializers.Serializer):
    inventory_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(min_value=1, default=1)


class OfflineInitialPaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        default=Decimal("0.00"),
    )
    payment_method = serializers.ChoiceField(
        choices=OfflinePaymentHistory.PaymentMethod.choices,
        default=OfflinePaymentHistory.PaymentMethod.CASH,
    )
    payment_screenshot = serializers.FileField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class OfflineOrderCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=OfflineCustomer.objects.filter(is_active=True)
    )
    order_date = serializers.DateField(required=False, allow_null=True)
    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )
    paid_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        default=Decimal("0.00"),
        required=False,
    )
    payment_method = serializers.ChoiceField(
        choices=OfflinePaymentHistory.PaymentMethod.choices,
        default=OfflinePaymentHistory.PaymentMethod.CASH,
        required=False,
    )
    payment_screenshot = serializers.FileField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")
    items = OfflineOrderItemCreateSerializer(many=True)
    initial_payment = OfflineInitialPaymentCreateSerializer(
        required=False, allow_null=True
    )

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("At least one order item is required.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        customer = attrs.get("customer")
        total_amount = attrs.get("total_amount", Decimal("0.00"))
        paid_amount = attrs.get("paid_amount", Decimal("0.00"))

        initial_payment = attrs.get("initial_payment")
        if initial_payment and initial_payment.get("amount"):
            paid_amount = Decimal(str(initial_payment["amount"]))

        if paid_amount > total_amount:
            raise serializers.ValidationError({
                "paid_amount": f"Paid amount (Rs. {paid_amount}) cannot exceed total amount (Rs. {total_amount})."
            })

        if user and hasattr(user, "franchise") and user.franchise:
            if (
                customer.franchise_id != user.franchise.id
                and getattr(user, "role", None) != "SuperAdmin"
            ):
                raise serializers.ValidationError({
                    "customer": "Customer does not belong to your assigned franchise."
                })

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user
        customer = validated_data["customer"]
        items_data = validated_data["items"]
        total_amount = validated_data["total_amount"]
        paid_amount = validated_data.get("paid_amount", Decimal("0.00"))
        payment_method = validated_data.get(
            "payment_method", OfflinePaymentHistory.PaymentMethod.CASH
        )
        payment_screenshot = validated_data.get("payment_screenshot")
        remarks = validated_data.get("remarks")
        order_date = validated_data.get("order_date")
        initial_payment_data = validated_data.get("initial_payment")

        return create_offline_order(
            user=user,
            customer=customer,
            items_data=items_data,
            total_amount=total_amount,
            paid_amount=paid_amount,
            payment_method=payment_method,
            payment_screenshot=payment_screenshot,
            remarks=remarks,
            order_date=order_date,
            initial_payment_data=initial_payment_data,
        )


class RecordPaymentCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=OfflineCustomer.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    order = serializers.PrimaryKeyRelatedField(
        queryset=OfflineOrder.objects.exclude(
            order_status=OfflineOrder.OrderStatus.CANCELLED
        ),
        required=False,
        allow_null=True,
    )
    order_code = serializers.CharField(required=False, allow_blank=True)
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    payment_method = serializers.ChoiceField(
        choices=OfflinePaymentHistory.PaymentMethod.choices,
        default=OfflinePaymentHistory.PaymentMethod.CASH,
    )
    payment_screenshot = serializers.FileField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        order = attrs.get("order")
        order_code = attrs.get("order_code")
        customer = attrs.get("customer")

        # 1. If there is nothing in the payload
        if not order and not order_code and not customer:
            raise serializers.ValidationError({
                "non_field_errors": "Either 'order' (or 'order_code') or 'customer' must be provided in the payload."
            })

        # Resolve order from order_code if provided
        if not order and order_code:
            try:
                order = OfflineOrder.objects.select_related("customer").get(
                    order_code=order_code
                )
                attrs["order"] = order
            except OfflineOrder.DoesNotExist:
                raise serializers.ValidationError({
                    "order_code": f"Order with code '{order_code}' does not exist."
                })

        # 2. If there is order in the payload then get the customer from order.customer
        if order:
            attrs["customer"] = order.customer

            if order.order_status == OfflineOrder.OrderStatus.CANCELLED:
                raise serializers.ValidationError({
                    "order": "Cannot record payment on a cancelled order."
                })

            if order.remaining_amount <= Decimal("0.00"):
                raise serializers.ValidationError({
                    "order": "This order is already fully paid."
                })

            amount = attrs.get("amount")
            if amount > order.remaining_amount:
                raise serializers.ValidationError({
                    "amount": (
                        f"Payment amount (Rs. {amount}) exceeds remaining credit balance "
                        f"(Rs. {order.remaining_amount})."
                    )
                })

            if user and hasattr(user, "franchise") and user.franchise:
                if (
                    order.franchise_id != user.franchise.id
                    and getattr(user, "role", None) != "SuperAdmin"
                ):
                    raise serializers.ValidationError({
                        "order": "Order does not belong to your assigned franchise."
                    })
        else:
            # 3. If there is only customer then make the order null
            attrs["order"] = None

            if user and hasattr(user, "franchise") and user.franchise:
                if (
                    customer.franchise_id != user.franchise.id
                    and getattr(user, "role", None) != "SuperAdmin"
                ):
                    raise serializers.ValidationError({
                        "customer": "Customer does not belong to your assigned franchise."
                    })

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        order = validated_data.get("order")
        customer = validated_data.get("customer")
        amount = validated_data["amount"]
        payment_method = validated_data["payment_method"]
        payment_screenshot = validated_data.get("payment_screenshot")
        remarks = validated_data.get("remarks")

        if order:
            return record_order_payment(
                order=order,
                amount=amount,
                payment_method=payment_method,
                payment_screenshot=payment_screenshot,
                remarks=remarks,
                user=user,
            )

        return OfflinePaymentHistory.objects.create(
            customer=customer,
            order=None,
            amount=amount,
            payment_method=payment_method,
            payment_screenshot=payment_screenshot,
            remarks=remarks,
            recorded_by=user,
        )


class OfflineOrderCreditReminderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.store_name", read_only=True)
    customer_contact_person = serializers.CharField(
        source="customer.contact_person", read_only=True
    )
    customer_phone = serializers.CharField(
        source="customer.phone_number", read_only=True
    )
    franchise_name = serializers.CharField(source="franchise.name", read_only=True)
    sales_person_name = serializers.CharField(
        source="sales_person.first_name", read_only=True
    )
    due_date = serializers.SerializerMethodField()
    days_passed = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    urgency_level = serializers.SerializerMethodField()

    class Meta:
        model = OfflineOrder
        fields = [
            "id",
            "order_code",
            "customer",
            "customer_name",
            "customer_contact_person",
            "customer_phone",
            "franchise",
            "franchise_name",
            "sales_person",
            "sales_person_name",
            "order_date",
            "due_date",
            "days_passed",
            "days_remaining",
            "is_overdue",
            "urgency_level",
            "order_status",
            "payment_status",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "remarks",
            "created_at",
        ]
        read_only_fields = fields

    def get_due_date(self, obj):
        return obj.order_date + timedelta(days=90)

    def get_days_passed(self, obj) -> int:
        return (timezone.localdate() - obj.order_date).days

    def get_days_remaining(self, obj) -> int:
        days_passed = self.get_days_passed(obj)
        return max(0, 90 - days_passed)

    def get_is_overdue(self, obj) -> bool:
        return self.get_days_passed(obj) >= 90

    def get_urgency_level(self, obj) -> str:
        days = self.get_days_passed(obj)
        if days >= 90:
            return "Overdue"
        elif days >= 75:
            return "Critical (Close to 3 Months)"
        elif days >= 60:
            return "Warning"
        return "Normal"


class OfflineSalesStatsSerializer(serializers.Serializer):
    total_customers = serializers.IntegerField()
    customers_with_pending_credit = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    pending_orders_count = serializers.IntegerField()
    close_to_due_orders_count = serializers.IntegerField()
    overdue_orders_count = serializers.IntegerField()
    total_order_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_paid_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_remaining_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
