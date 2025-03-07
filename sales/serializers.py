from rest_framework import serializers
from .models import Inventory, Order, OrderProduct, Product,InventoryChangeLog, InventoryRequest
from account.models import CustomUser
from account.serializers import CustomUserSerializer, UserSmallSerializer

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description','image']

class RawMaterialSerializer(serializers.ModelSerializer):
    product=ProductSerializer(read_only=True)
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
        fields = ['id', 'distributor', 'franchise', 'factory', 'product', 'product_id', 'quantity', 'status']
        read_only_fields = ['distributor', 'franchise', 'factory']  # These will be set in the view

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
    order_products = OrderProductSerializer(many=True)
    sales_person = UserSmallSerializer(read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'full_name', 'city', 'delivery_address', 'landmark',
                  'phone_number', 'alternate_phone_number', 'payment_method',
                  'payment_screenshot', 'order_status', 'date', 'created_at', 'updated_at', 'order_products',
                  'total_amount', 'remarks', 'sales_person']

    def create(self, validated_data):
        # Extract order_products data from validated_data
        order_products_data = validated_data.pop('order_products')
        
        # Get the user from the context
        user = self.context['request'].user
        
        # Remove sales_person and franchise from validated_data if they exist
        validated_data.pop('sales_person', None)
        validated_data.pop('franchise', None)
        
        # Create the order instance
        order = Order.objects.create(
            sales_person=user,
            franchise=user.franchise,
            **validated_data
        )
        
        # Create each order product
        for order_product_data in order_products_data:
            OrderProduct.objects.create(order=order, **order_product_data)
        
        return order

    def update(self, instance, validated_data):
        order_products_data = validated_data.pop('order_products', None)
        instance = super().update(instance, validated_data)

        if order_products_data is not None:
            instance.order_products.all().delete()
            for order_product_data in order_products_data:
                OrderProduct.objects.create(order=instance, **order_product_data)

        return instance
    

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description','image']

class SalesPersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email']  # Add more fields as needed

class OrderDetailSerializer(serializers.ModelSerializer):
    sales_person = SalesPersonSerializer()
    order_products = OrderProductSerializer(many=True)  # Include order products

    class Meta:
        model = Order
        fields = ['id', 'order_status', 'total_amount', 'created_at', 'sales_person', 'order_products']  # Add more fields as needed


class InventoryRequestSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        write_only=True,
        source='product',
        required=False
    )

    class Meta:
        model = InventoryRequest
        fields = ['id', 'product', 'product_id', 'quantity', 'factory', 'distributor', 'status', 'total_amount', 'created_at']
        read_only_fields = ['total_amount', 'user']

    def validate(self, data):
        user = self.context['request'].user
        
        # Skip validation for updates (PATCH/PUT requests)
        if self.instance is not None:
            return data

        factory = data.get('factory')
        distributor = data.get('distributor')

        # Validation for create only
        if not self.instance:
            # Check that only one destination is specified
            if factory and distributor:
                raise serializers.ValidationError("Cannot request from both factory and distributor")
            if not factory and not distributor:
                raise serializers.ValidationError("Must specify either factory or distributor")

            # Franchise validation
            if user.role == 'Franchise':
                if not hasattr(user, 'franchise'):
                    raise serializers.ValidationError("User is not associated with a franchise")
                
                if factory:
                    raise serializers.ValidationError("Franchise can only request from distributor")
                
                # Validate requesting from assigned distributor
                if distributor != user.franchise.distributor:
                    raise serializers.ValidationError("Can only request from your assigned distributor")

            # Distributor validation
            elif user.role == 'Distributor':
                if not hasattr(user, 'distributor'):
                    raise serializers.ValidationError("User is not associated with a distributor")
                
                if distributor:
                    raise serializers.ValidationError("Distributor cannot request from another distributor")
                
                # Validate requesting from factory
                if not factory:
                    raise serializers.ValidationError("Distributor must request from factory")

            else:
                raise serializers.ValidationError(f"Users with role {user.role} cannot make inventory requests")

            # Check for existing pending requests for the same product
            existing_request = InventoryRequest.objects.filter(
                user=user,
                product=data['product'],
                status='Pending'
            )
            if factory:
                existing_request = existing_request.filter(factory=factory)
            if distributor:
                existing_request = existing_request.filter(distributor=distributor)
                
            if existing_request.exists():
                raise serializers.ValidationError("You already have a pending request for this product")

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class TopSalespersonSerializer(serializers.ModelSerializer):
    franchise = serializers.StringRelatedField(read_only=True)
    total_sales = serializers.FloatField(read_only=True)
    sales_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'phone_number', 'franchise', 'total_sales', 'sales_count')