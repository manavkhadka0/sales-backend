from rest_framework import serializers

from .models import DarazLocation


class DarazLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DarazLocation
        fields = [
            "id",
            "city",
            "area",
            "l4_id",
        ]
        read_only_fields = ["created_at", "updated_at"]


class DarazLocationImportSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)

    def validate_file(self, value):
        if not value.name.lower().endswith(".csv"):
            raise serializers.ValidationError("Only CSV files are supported.")
        return value
