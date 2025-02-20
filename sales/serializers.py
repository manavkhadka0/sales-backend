from rest_framework import serializers
from .models import Inventory, Order, OrderProduct, Product,InventoryChangeLog, InventoryRequest
from account.models import CustomUser
from account.serializers import CustomUserSerializer

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description','image']

class InventorySerializer(serializers.ModelSerializer):
    product=ProductSerializer(read_only=True)
    class Meta:
        model = Inventory
        fields = ['id', 'distributor', 'product', 'quantity']

class InventoryChangeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryChangeLog
        fields = '__all__'  # You can specify fields explicitly if needed


class OrderProductSerializer(serializers.ModelSerializer):
    product = InventorySerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Inventory.objects.all(),  # Changed from Product to Inventory
        write_only=True,
        source='product'
    )

    class Meta:
        model = OrderProduct
        fields = ['id', 'product', 'product_id', 'quantity']

class OrderSerializer(serializers.ModelSerializer):
    order_products = OrderProductSerializer(many=True)
    sales_person = CustomUserSerializer(read_only=True)
    franchise_name = serializers.CharField(source='franchise.name', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'full_name', 'city', 'delivery_address', 'landmark',
                  'phone_number', 'alternate_phone_number', 'delivery_charge', 'payment_method',
                  'payment_screenshot', 'order_status', 'date', 'created_at', 'updated_at', 'order_products',
                  'total_amount', 'remarks', 'sales_person', 'franchise_name']

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