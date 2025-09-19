from django.utils import timezone
from rest_framework import serializers
from .models import Inventory, Order, OrderProduct, Product, InventoryChangeLog, InventoryRequest, PromoCode, Location
from account.models import CustomUser
from account.serializers import SmallUserSerializer, UserSmallSerializer
from logistics.serializers import OrderCommentSerializer


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'image']


class RawMaterialSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Inventory
        fields = ['id', 'product', 'quantity', 'status']


class InventorySerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        write_only=True,
        source='product'
    )

    class Meta:
        model = Inventory
        fields = ['id', 'distributor', 'franchise', 'factory',
                  'product', 'product_id', 'quantity', 'status']
        read_only_fields = ['distributor', 'franchise',
                            'factory']  # These will be set in the view


class InventoryChangeLogSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()

    class Meta:
        model = InventoryChangeLog
        fields = ['id', 'product_name', 'old_quantity', 'new_quantity',
                  'action', 'user_name', 'organization', 'changed_at']

    def get_product_name(self, obj):
        return obj.inventory.product.name if obj.inventory else "Unknown Product"

    def get_user_name(self, obj):
        return obj.user.username if obj.user else "Unknown User"

    def get_organization(self, obj):
        if not obj.inventory:
            return "Unknown Organization"

        if obj.inventory.factory:
            return f"Factory: {obj.inventory.factory}"
        elif obj.inventory.distributor:
            return f"Distributor: {obj.inventory.distributor}"
        elif obj.inventory.franchise:
            return f"Franchise: {obj.inventory.franchise}"
        return "No Organization"


class InventorySmallSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    class Meta:
        model = Inventory
        fields = ['id', 'product', 'quantity', 'status']

    def get_product(self, obj):
        return {
            'id': obj.product.id,
            'name': obj.product.name
        }


class ProductSmallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name']


class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = ['id', 'code', 'discount_percentage', 'valid_from',
                  'valid_until', 'max_uses', 'times_used', 'is_active']
        read_only_fields = ['times_used']

    def validate(self, data):
        if data.get('valid_from') and data.get('valid_until'):
            if data['valid_until'] <= data['valid_from']:
                raise serializers.ValidationError(
                    "Valid until date must be after valid from date")
        if data.get('discount_percentage') and (data['discount_percentage'] <= 0 or data['discount_percentage'] > 100):
            raise serializers.ValidationError(
                "Discount percentage must be between 0 and 100")

        return data


class ValidatePromoCodeSerializer(serializers.ModelSerializer):

    class Meta:
        model = PromoCode
        fields = ['id', 'code']


class OrderProductSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Inventory.objects.all(),
        write_only=True,
        source='product'
    )

    class Meta:
        model = OrderProduct
        fields = ['id', 'product', 'product_id', 'quantity']

    def get_product(self, obj):
        return {
            'id': obj.product.id,
            'name': obj.product.product.name
        }


class OrderSerializer(serializers.ModelSerializer):
    sales_person = UserSmallSerializer(read_only=True)
    order_products = OrderProductSerializer(many=True, required=False)
    promo_code = serializers.CharField(required=False, allow_null=True)
    payment_screenshot = serializers.FileField(required=False, allow_null=True)
    dash_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    dash_location_name = serializers.SerializerMethodField(read_only=True)
    ydm_rider = serializers.SerializerMethodField(read_only=True)
    ydm_rider_name = serializers.SerializerMethodField(read_only=True)
    comments = serializers.SerializerMethodField(read_only=True)
    sent_to_ydm_date = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_code', 'sales_person', 'full_name', 'city', 'delivery_address', 'landmark',
                  'phone_number', 'alternate_phone_number', 'payment_method', 'dash_location',
                  'payment_screenshot', 'order_status', 'date', 'created_at', 'updated_at',
                  'order_products', 'total_amount', 'delivery_charge', 'remarks', 'promo_code',
                  'prepaid_amount', 'delivery_type', 'logistics', 'dash_location_name',
                  'dash_tracking_code', 'ydm_rider', 'ydm_rider_name', 'comments', 'sent_to_ydm_date']

    def get_ydm_rider(self, obj):
        # Get the assigned user using select_related to optimize the query
        assignment = obj.assign_orders.select_related('user').first()
        return assignment.user.phone_number if assignment and assignment.user else None

    def get_ydm_rider_name(self, obj):
        assignment = obj.assign_orders.select_related('user').first()
        return assignment.user.first_name if assignment and assignment.user else None

    def get_dash_location_name(self, obj):
        return obj.dash_location.name if obj.dash_location else None

    def get_comments(self, obj):
        latest_comment = obj.comments.order_by('-id').first()
        if latest_comment:
            return OrderCommentSerializer(latest_comment).data
        return None

    def get_sent_to_ydm_date(self, obj):
        sent_to_ydm_log = obj.change_logs.filter(
            new_status='Sent to YDM'
        ).order_by('changed_at').first()

        if sent_to_ydm_log:
            return sent_to_ydm_log.changed_at
        return None

    def create(self, validated_data):
        order_products_data = validated_data.pop('order_products', [])
        promo_code = validated_data.pop('promo_code', None)
        promo_code_instance = None

        # ✅ Validate promo code
        if promo_code:
            try:
                promo_code_instance = PromoCode.objects.get(
                    code=promo_code,
                    is_active=True,
                    valid_from__lte=timezone.now(),
                    valid_until__gte=timezone.now()
                )
            except PromoCode.DoesNotExist:
                raise serializers.ValidationError(
                    {"promo_code": "Invalid promo code"})

        # ✅ Create Order
        order = Order.objects.create(
            **validated_data, promo_code=promo_code_instance)

        # ✅ Create Order Products
        for order_product_data in order_products_data:
            product = order_product_data['product']
            quantity = order_product_data['quantity']
            OrderProduct.objects.create(
                order=order, product=product, quantity=quantity)

        # ✅ Update promo code usage count
        if promo_code_instance:
            promo_code_instance.times_used += 1
            promo_code_instance.save()

        return order

    def update(self, instance, validated_data):
        order_products_data = validated_data.pop('order_products', None)
        instance = super().update(instance, validated_data)

        # ✅ Update order products if provided
        if order_products_data is not None:
            instance.order_products.all().delete()
            for order_product_data in order_products_data:
                OrderProduct.objects.create(
                    order=instance, **order_product_data)

        return instance


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'image']


class SalesPersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email']  # Add more fields as needed


class OrderDetailSerializer(serializers.ModelSerializer):
    sales_person = SalesPersonSerializer()
    order_products = OrderProductSerializer(
        many=True)  # Include order products

    class Meta:
        model = Order
        fields = ['id', 'order_status', 'total_amount', 'created_at',
                  'sales_person', 'order_products']  # Add more fields as needed


class InventoryRequestSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        write_only=True,
        source='product',
        required=False
    )

    user = UserSmallSerializer(read_only=True)

    class Meta:
        model = InventoryRequest
        fields = ['id', 'user', 'product', 'product_id', 'quantity',
                  'factory', 'distributor', 'franchise', 'status', 'total_amount', 'created_at']
        read_only_fields = ['total_amount', 'user']

    def validate(self, data):
        user = self.context['request'].user

        # Skip validation for updates (PATCH/PUT requests)
        if self.instance is not None:
            return data

        factory = data.get('factory')
        distributor = data.get('distributor')
        franchise = data.get('franchise')

        # Validation for create only
        if not self.instance:
            # Check that at least one destination is specified
            if not any([factory, distributor, franchise]):
                raise serializers.ValidationError(
                    "Must specify at least one destination (factory, distributor, or franchise)")

            # Franchise validation
            if user.role == 'Franchise':
                if not hasattr(user, 'franchise'):
                    raise serializers.ValidationError(
                        "User is not associated with a franchise")

            # Distributor validation
            elif user.role == 'Distributor':
                if not hasattr(user, 'distributor'):
                    raise serializers.ValidationError(
                        "User is not associated with a distributor")

            else:
                raise serializers.ValidationError(
                    f"Users with role {user.role} cannot make inventory requests")

            # Check for existing pending requests for the same product
            existing_request = InventoryRequest.objects.filter(
                user=user,
                product=data['product'],
                status='Pending'
            )
            if factory:
                existing_request = existing_request.filter(factory=factory)
            if distributor:
                existing_request = existing_request.filter(
                    distributor=distributor)
            if franchise:
                existing_request = existing_request.filter(franchise=franchise)

            if existing_request.exists():
                raise serializers.ValidationError(
                    "You already have a pending request for this product")

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class TopSalespersonSerializer(serializers.ModelSerializer):
    total_sales = serializers.FloatField(read_only=True)
    sales_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name',
                  'total_sales', 'sales_count')


class ProductSalesSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    quantity_sold = serializers.IntegerField()


class SalesPersonStatisticsSerializer(serializers.Serializer):
    user = SmallUserSerializer()
    total_orders = serializers.IntegerField()
    total_cancelled_orders = serializers.IntegerField()
    total_amount = serializers.FloatField()
    total_cancelled_amount = serializers.FloatField()
    total_delivery_charge = serializers.FloatField()
    product_sales = ProductSalesSerializer(many=True)
    cancelled_product_sales = ProductSalesSerializer(many=True)


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'coverage_areas']


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class InventorySnapshotSerializer(serializers.Serializer):
    inventory_id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    quantity = serializers.IntegerField()
