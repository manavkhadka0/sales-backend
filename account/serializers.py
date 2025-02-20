from rest_framework import serializers
from .models import CustomUser,Distributor,Franchise

class DistributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distributor
        fields = '__all__'

class CustomUserSerializer(serializers.ModelSerializer):
    distributor = serializers.PrimaryKeyRelatedField(queryset=Distributor.objects.all(), write_only=True, required=False, allow_null=True)
    franchise = serializers.PrimaryKeyRelatedField(queryset=Franchise.objects.all(), write_only=True, required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 
                 'phone_number', 'address', 'role', 'distributor', 'franchise', 'password')
        read_only_fields = ('username',)  # Make username read-only since we'll set it automatically

    def create(self, validated_data):
        password = validated_data.pop('password')  # Remove password from validated data
        phone_number = validated_data.get('phone_number')
        validated_data['username'] = phone_number  # Set username to phone number
        
        # Handle null values for distributor and franchise
        if 'distributor' in validated_data and validated_data['distributor'] is None:
            validated_data.pop('distributor')
        if 'franchise' in validated_data and validated_data['franchise'] is None:
            validated_data.pop('franchise')
        
        user = CustomUser(**validated_data)  # Create user instance
        user.set_password(password)  # Hash the password
        user.save()  # Save the user instance
        return user

class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
