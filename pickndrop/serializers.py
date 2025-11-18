from rest_framework import serializers

from .models import PickNDrop


class PickNDropSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickNDrop
        fields = "__all__"
