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
    class Meta:
        model = InventoryRequest
        fields = '__all__'

    def create(self, validated_data):
        # Get the user from the context
        user = self.context['request'].user
        validated_data['user'] = user  # Set the user in the validated data
        return super().create(validated_data)  # Call the parent class's create method

class TopSalespersonSerializer(serializers.ModelSerializer):
    franchise = serializers.StringRelatedField(read_only=True)
    total_sales = serializers.FloatField(read_only=True)
    sales_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'phone_number', 'franchise', 'total_sales', 'sales_count')