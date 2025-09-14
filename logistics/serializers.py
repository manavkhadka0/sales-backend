from rest_framework import serializers
from . models import OrderChangeLog, OrderComment, AssignOrder, FranchisePaymentLog
from sales.models import Order
from account.models import CustomUser
from account.serializers import SmallUserSerializer


class OrderChangeLogSerializer(serializers.ModelSerializer):
    user = SmallUserSerializer()

    class Meta:
        model = OrderChangeLog
        fields = '__all__'


class OrderCommentSerializer(serializers.ModelSerializer):

    class Meta:
        model = OrderComment
        fields = ['id', 'order', 'user', 'comment', 'created_at', 'updated_at']


class OrderCommentDetailSerializer(serializers.ModelSerializer):
    user = SmallUserSerializer(read_only=True)

    class Meta:
        model = OrderComment
        fields = ['id', 'order', 'user', 'comment', 'created_at', 'updated_at']


class AssignOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignOrder
        fields = ["id", "order", "user", "assigned_at"]


class FranchisePaymentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = FranchisePaymentLog
        fields = ["id", "franchise", "paid_by", "amount_paid",
                  "payment_method", "notes", "payment_date"]
