from rest_framework import serializers
from .models import CustomUser,Distributor,Franchise

class DistributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distributor
        fields = '__all__'

class CustomUserSerializer(serializers.ModelSerializer):
    distributor = serializers.PrimaryKeyRelatedField(queryset=Distributor.objects.all(), write_only=True,required=False)
    franchise= serializers.PrimaryKeyRelatedField(queryset=Franchise.objects.all(), write_only=True,required=False)

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 
                  'phone_number', 'address', 'role', 'is_active', 'distributor','franchise','password')

    def create(self, validated_data):
        password = validated_data.pop('password')  # Remove password from validated data
        user = CustomUser(**validated_data)  # Create user instance
        user.set_password(password)  # Hash the password
        user.save()  # Save the user instance
        return user



class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
