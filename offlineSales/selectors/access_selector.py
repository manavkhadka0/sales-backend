from offlineSales.models import OfflineSalesAccess


def get_offline_sales_access_queryset():
    """
    Returns an optimized queryset for OfflineSalesAccess with related user and granted_by fields.
    """
    return (
        OfflineSalesAccess.objects.select_related("user", "granted_by")
        .only(
            "id",
            "granted_at",
            "user__id",
            "user__username",
            "user__first_name",
            "user__last_name",
            "user__email",
            "user__phone_number",
            "user__role",
            "granted_by__id",
            "granted_by__username",
            "granted_by__first_name",
            "granted_by__last_name",
        )
        .order_by("-granted_at")
    )
