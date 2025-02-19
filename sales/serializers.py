from rest_framework import serializers
from .models import Inventory, Order, OrderProduct, Product,InventoryChangeLog, InventoryRequest
from account.models import CustomUser
from account.serializers import CustomUserSerializer

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'description']

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
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), write_only=True, source='product')

    class Meta:
        model = OrderProduct
        fields = ['id', 'product', 'product_id', 'quantity', 'discount', 'get_total_price']

class OrderSerializer(serializers.ModelSerializer):
    order_products = OrderProductSerializer(many=True)
    sales_person=CustomUserSerializer(read_only=True)
    class Meta:
        model = Order
        fields = ['id','full_name', 'city', 'delivery_address', 'landmark',
                  'phone_number', 'alternate_phone_number', 'delivery_charge', 'payment_method',
                  'payment_screenshot', 'order_status', 'date','created_at', 'updated_at', 'order_products',
                  'total_amount', 'remarks','sales_person']

    def create(self, validated_data):
        order_products_data = validated_data.pop('order_products')
        total_amount = 0  # Initialize total_amount
        order = Order.objects.create(**validated_data)

        for order_product_data in order_products_data:
            # Ensure get_total_price is called correctly
            product = OrderProduct(**order_product_data)  # Create an instance
            total_amount += product.get_total_price()  # Call the method

            OrderProduct.objects.create(order=order, **order_product_data)

        order.total_amount = total_amount  # Set the total_amount
        order.save()  # Save the order with the updated total_amount
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
        fields = ['id', 'name', 'price', 'description']

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