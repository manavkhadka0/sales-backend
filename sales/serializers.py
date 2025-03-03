from rest_framework import serializers
from .models import Inventory, Order, OrderProduct, Product,InventoryChangeLog, InventoryRequest
from account.models import CustomUser
from account.serializers import CustomUserSerializer, UserSmallSerializer

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description','image']

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
    class Meta:
        model = InventoryChangeLog
        fields = '__all__'  # You can specify fields explicitly if needed


class OrderProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Inventory.objects.all(),
        write_only=True,
        source='product'
    )

    class Meta:
        model = OrderProduct
        fields = ['id', 'product', 'product_id', 'quantity']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Replace product data with actual product info instead of inventory
        if instance.product:
            representation['product'] = ProductSerializer(instance.product.product).data
        return representation

class OrderSerializer(serializers.ModelSerializer):
    order_products = OrderProductSerializer(many=True)
    sales_person = UserSmallSerializer(read_only=True)
    franchise_name = serializers.CharField(source='franchise.name', read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'full_name', 'city', 'delivery_address', 'landmark',
                  'phone_number', 'alternate_phone_number', 'delivery_charge', 'payment_method',
                  'payment_screenshot', 'order_status', 'date', 'created_at', 'updated_at', 'order_products',
                  'total_amount', 'remarks', 'sales_person', 'franchise_name']

    def validate_order_products(self, order_products_data):
        """
        Validate that all products exist and have sufficient inventory
        """
        user = self.context['request'].user
        franchise = user.franchise if hasattr(user, 'franchise') else None

        for item in order_products_data:
            inventory = item['product']  # This is now the Inventory instance
            quantity = item['quantity']

            if inventory.quantity < quantity:
                raise serializers.ValidationError(
                    f"Insufficient inventory for product {inventory.product.name}. "
                    f"Available: {inventory.quantity}, Requested: {quantity}"
                )

            # Verify the inventory belongs to the correct entity
            if user.role == 'SalesPerson' and user.sales_person == 'Franchise':
                if inventory.franchise != franchise:
                    raise serializers.ValidationError("Invalid inventory for this franchise")
            elif user.role == 'SuperAdmin':
                if inventory.factory != user.factory:
                    raise serializers.ValidationError("Invalid inventory for this factory")
            elif user.role == 'Distributor':
                if inventory.distributor != user.distributor:
                    raise serializers.ValidationError("Invalid inventory for this distributor")
            else:
                raise serializers.ValidationError("Invalid user role")

        return order_products_data

    def create(self, validated_data):
        order_products_data = validated_data.pop('order_products')
        user = self.context['request'].user
        
        # Remove sales_person and franchise from validated_data if they exist
        validated_data.pop('sales_person', None)
        validated_data.pop('franchise', None)
        
        # Set franchise based on user role
        franchise = None
        if user.role in ['SalesPerson', 'Franchise']:
            franchise = user.franchise
        
        # Create the order instance
        order = Order.objects.create(
            sales_person=user,
            franchise=franchise,
            **validated_data
        )
        
        # Create order products and update inventory
        for order_product_data in order_products_data:
            inventory = order_product_data['product']  # This is now the Inventory instance
            quantity = order_product_data['quantity']

            # Create the order product
            OrderProduct.objects.create(
                order=order,
                product=inventory,  # Directly use the inventory instance
                quantity=quantity
            )

            # Update inventory
            old_quantity = inventory.quantity
            inventory.quantity -= quantity
            inventory.save()

            # Create inventory change log
            InventoryChangeLog.objects.create(
                inventory=inventory,
                user=user,
                old_quantity=old_quantity,
                new_quantity=inventory.quantity,
                action='update'
            )
        
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