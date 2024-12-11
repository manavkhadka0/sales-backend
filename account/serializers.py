from rest_framework import serializers
from .models import CustomUser,Distributor


class CustomUserSerializer(serializers.ModelSerializer):
    distributor = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 
                  'phone_number', 'address', 'role', 'is_active', 'distributor')

    def get_distributor(self, obj):
        if obj.distributor:
            return obj.distributor.name
        return None

class DistributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distributor
        fields = '__all__'

class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
