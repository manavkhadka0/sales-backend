from rest_framework import serializers
from .models import CustomUser,Distributor


class CustomUserSerializer(serializers.ModelSerializer):
    distributor = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 
                  'phone_number', 'address', 'role', 'is_active', 'distributor','password')

    def get_distributor(self, obj):
        if obj.distributor:
            return obj.distributor.name
        return None

    def create(self, validated_data):
        password = validated_data.pop('password')  # Remove password from validated data
        user = CustomUser(**validated_data)  # Create user instance
        user.set_password(password)  # Hash the password
        user.save()  # Save the user instance
        return user

class DistributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distributor
        fields = '__all__'

class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
