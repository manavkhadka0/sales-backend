from rest_framework import serializers
from .models import CustomUser, Distributor, Franchise, Factory, Logistics
from sales.models import Order


class FactorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Factory
        fields = '__all__'


class DistributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distributor
        fields = '__all__'


class FranchiseSerializer(serializers.ModelSerializer):

    class Meta:
        model = Franchise
        fields = '__all__'


class YDMFranchiseSerializer(serializers.ModelSerializer):
    new_order_count = serializers.SerializerMethodField()
    franchise_contact_numbers = serializers.SerializerMethodField()

    class Meta:
        model = Franchise
        fields = ['id', 'name', 'short_form', 'distributor',
                  'new_order_count', 'franchise_contact_numbers']

    def get_new_order_count(self, obj):
        return Order.objects.filter(logistics='YDM', franchise=obj, order_status='Sent to YDM').count()

    def get_franchise_contact_numbers(self, obj):
        users = CustomUser.objects.filter(
            franchise=obj).values('first_name', 'last_name', 'phone_number')
        return list(users)


class UserSerializer(serializers.ModelSerializer):
    factory = serializers.StringRelatedField(read_only=True)
    distributor = serializers.StringRelatedField(read_only=True)
    franchise = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'first_name', 'last_name', 'email',
                  'phone_number', 'address', 'role', 'factory', 'distributor', 'franchise')


class CustomUserSerializer(serializers.ModelSerializer):
    distributor = serializers.PrimaryKeyRelatedField(
        queryset=Distributor.objects.all(), write_only=True, required=False, allow_null=True)
    franchise = serializers.PrimaryKeyRelatedField(
        queryset=Franchise.objects.all(), write_only=True, required=False, allow_null=True)
    factory = serializers.PrimaryKeyRelatedField(
        queryset=Factory.objects.all(), write_only=True, required=False, allow_null=True)
    password = serializers.CharField(write_only=True,)
    distributor_name = serializers.CharField(
        source='distributor.name', read_only=True, allow_null=True, required=False)
    franchise_name = serializers.CharField(
        source='franchise.name', read_only=True, allow_null=True, required=False)
    factory_name = serializers.CharField(
        source='factory.name', read_only=True, allow_null=True, required=False)
    franchise_id = serializers.CharField(
        source='franchise.id', read_only=True, allow_null=True, required=False)

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'first_name', 'last_name', 'email',
                  'phone_number', 'address', 'role', 'factory', 'distributor', 'franchise', 'password', 'distributor_name', 'franchise_name', 'factory_name', 'franchise_id')
        # Make username read-only since we'll set it automatically
        read_only_fields = ('username',)

    def create(self, validated_data):
        password = validated_data.pop('password')
        phone_number = validated_data.get('phone_number')

        # Check if user with this phone number already exists
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError({
                'phone_number': 'A user with this phone number already exists.'
            })

        validated_data['username'] = phone_number

        # Handle relationships between factory, distributor, and franchise
        role = validated_data.get('role')
        franchise = validated_data.get('franchise')
        distributor = validated_data.get('distributor')
        factory = validated_data.get('factory')

        if role == 'SalesPerson' and franchise:
            # For salesperson, check if franchise has distributor
            if hasattr(franchise, 'distributor') and franchise.distributor:
                # If franchise has distributor, set both distributor and factory
                validated_data['distributor'] = franchise.distributor
                validated_data['factory'] = franchise.distributor.factory
            else:
                # If franchise has no distributor, don't set distributor
                # but set factory from the franchise (login user's franchise)
                if hasattr(franchise, 'factory') and franchise.factory:
                    validated_data['factory'] = franchise.factory
                elif factory:
                    # Fallback to user input factory if franchise doesn't have one
                    validated_data['factory'] = factory
        elif distributor and franchise:
            # If both distributor and franchise exist, set factory from distributor
            validated_data['factory'] = distributor.factory
        elif franchise and not distributor:
            # If only franchise exists, get distributor and factory from franchise
            # Only set distributor if franchise has one
            if hasattr(franchise, 'distributor') and franchise.distributor:
                validated_data['distributor'] = franchise.distributor
                validated_data['factory'] = franchise.distributor.factory
            else:
                # If franchise has no distributor, use the factory from user input
                if factory:
                    validated_data['factory'] = factory

        # Handle null values
        if 'distributor' in validated_data and validated_data['distributor'] is None:
            validated_data.pop('distributor')
        if 'franchise' in validated_data and validated_data['franchise'] is None:
            validated_data.pop('franchise')
        if 'factory' in validated_data and validated_data['factory'] is None:
            validated_data.pop('factory')

        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSmallSerializer(serializers.ModelSerializer):
    franchise = serializers.StringRelatedField(read_only=True)
    distributor = serializers.StringRelatedField(read_only=True)
    factory = serializers.StringRelatedField(read_only=True)
    franchise_contact = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ('id', 'first_name', 'last_name', 'phone_number',
                  'franchise', 'distributor', 'factory', 'franchise_contact')

    def get_franchise_contact(self, obj):
        return CustomUser.objects.filter(franchise=obj.franchise).values('phone_number')


class SmallUserSerializer(serializers.ModelSerializer):
    franchise = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ('id', 'first_name', 'last_name', 'email', 'phone_number', 'role',
                  'franchise', 'address')


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class ChangePasswordSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    class Meta:
        model = CustomUser
        fields = ['phone_number', 'new_password']


class LogisticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Logistics
        fields = '__all__'
