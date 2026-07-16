from rest_framework import serializers

from .models import YDMLogistics


class YDMLogisticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = YDMLogistics
        fields = ["id", "franchise", "api_key"]
        read_only_fields = ["franchise"]

