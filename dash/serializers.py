from rest_framework import serializers
from .models import Dash


class DashSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dash
        fields = '__all__'


class DashLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
