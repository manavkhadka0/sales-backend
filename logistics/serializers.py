from rest_framework import serializers
from . models import OrderChangeLog, OrderComment
from account.serializers import SmallUserSerializer


class OrderChangeLogSerializer(serializers.ModelSerializer):
    user = SmallUserSerializer()

    class Meta:
        model = OrderChangeLog
        fields = '__all__'


class OrderCommentSerializer(serializers.ModelSerializer):
    user = SmallUserSerializer()

    class Meta:
        model = OrderComment
        fields = '__all__'
