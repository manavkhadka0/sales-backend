from rest_framework import serializers
from .models import Inventory, Order, OrderProduct, Product

class InventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inventory
        fields = ['id', 'distributor', 'product', 'quantity']

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'description']

class OrderProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), write_only=True, source='product')

    class Meta:
        model = OrderProduct
        fields = ['id', 'product', 'product_id', 'quantity', 'discount', 'get_total_price']

class OrderSerializer(serializers.ModelSerializer):
    order_products = OrderProductSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'full_name', 'city', 'delivery_address', 'landmark',
                  'phone_number', 'alternate_phone_number', 'delivery_charge', 'payment_method',
                  'payment_screenshot', 'order_status', 'created_at', 'updated_at', 'order_products',
                  'total_amount', 'remarks']

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