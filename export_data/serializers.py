from rest_framework import serializers


class OrderSelectedExportSerializer(serializers.Serializer):
    order_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False,
        help_text="List of integer Order IDs to export",
    )
    export_format = serializers.ChoiceField(
        choices=["xlsx", "csv"],
        default="xlsx",
        required=False,
        help_text="File format to export: 'xlsx' (default) or 'csv'",
    )
    weight = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1.0,
        required=False,
        help_text="Parcel weight in kg to write in the weight column (default: 1.0)",
    )
    store_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional Store Name override. If omitted, matched from each order's franchise.",
    )

    def to_internal_value(self, data):
        # Support QueryDict / dict where order_ids may be passed as comma-separated or list
        if hasattr(data, "copy"):
            data = data.copy()
        else:
            data = dict(data)

        order_ids = data.get("order_ids")
        if isinstance(order_ids, str):
            cleaned = order_ids.strip("[]() ")
            if cleaned:
                try:
                    data["order_ids"] = [
                        int(item.strip()) for item in cleaned.split(",") if item.strip()
                    ]
                except ValueError:
                    raise serializers.ValidationError({
                        "order_ids": "All order IDs must be valid integers."
                    })
            else:
                data["order_ids"] = []

        return super().to_internal_value(data)

    def validate_order_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one order ID must be provided.")
        return value
