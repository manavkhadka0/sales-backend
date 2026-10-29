from datetime import timedelta
from typing import Optional, Union

from django.db.models import Q, QuerySet
from django.utils import timezone

from tracking.constants import HEARTBEAT_TIMEOUT_MINUTES, TrackingStatus
from tracking.models import SalesPersonLocation, SalesPersonLocationHistory


def get_salesperson_locations_qs(
    user,
    franchise_id: Optional[Union[int, str]] = None,
    distributor_id: Optional[Union[int, str]] = None,
    is_online: Optional[bool] = None,
    tracking_status: Optional[str] = None,
) -> QuerySet[SalesPersonLocation]:
    """
    Returns an optimized QuerySet of live salesperson locations, selecting
    related salesperson, franchise, and distributor information to avoid N+1 queries.
    Strictly isolates data based on the requesting user's organizational scope.
    Supports heartbeat timeout verification for active status.
    """
    qs = (
        SalesPersonLocation.objects
        .select_related(
            "salesperson",
            "salesperson__franchise",
        )
        .only(
            "id",
            "latitude",
            "longitude",
            "accuracy",
            "is_online",
            "last_updated_at",
            "salesperson__id",
            "salesperson__username",
            "salesperson__first_name",
            "salesperson__last_name",
            "salesperson__phone_number",
            "salesperson__role",
            "salesperson__franchise__id",
            "salesperson__franchise__name",
        )
        .order_by("-last_updated_at")
    )

    # Apply role-based scoping
    if (
        getattr(user, "is_superuser", False)
        or getattr(user, "role", None) == "SuperAdmin"
    ):
        if franchise_id is not None:
            qs = qs.filter(salesperson__franchise_id=franchise_id)
        if distributor_id is not None:
            qs = qs.filter(salesperson__distributor_id=distributor_id)
    elif getattr(user, "role", None) == "Distributor":
        user_distributor_id = getattr(user, "distributor_id", None)
        qs = qs.filter(
            Q(salesperson__distributor_id=user_distributor_id)
            | Q(salesperson__franchise__distributor_id=user_distributor_id)
        )
        if franchise_id is not None:
            qs = qs.filter(salesperson__franchise_id=franchise_id)
    elif getattr(user, "role", None) == "Franchise":
        user_franchise_id = getattr(user, "franchise_id", None)
        qs = qs.filter(salesperson__franchise_id=user_franchise_id)
    elif getattr(user, "role", None) in ["Offline_SalesPerson", "SalesPerson"]:
        qs = qs.filter(salesperson_id=user.id)
    else:
        return SalesPersonLocation.objects.none()

    # Heartbeat threshold calculation
    threshold = timezone.now() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)

    if tracking_status:
        val = str(tracking_status).upper()
        if val == TrackingStatus.ONLINE:
            qs = qs.filter(is_online=True, last_updated_at__gte=threshold)
        elif val == TrackingStatus.INACTIVE:
            qs = qs.filter(is_online=True, last_updated_at__lt=threshold)
        elif val == TrackingStatus.OFFLINE:
            qs = qs.filter(is_online=False)
    elif is_online is not None:
        if is_online is True:
            # Actively broadcasting: is_online=True AND last_updated_at >= threshold
            qs = qs.filter(is_online=True, last_updated_at__gte=threshold)
        else:
            # Either explicitly clocked out OR signal dropped > 5 mins
            qs = qs.filter(Q(is_online=False) | Q(last_updated_at__lt=threshold))

    return qs


def get_salesperson_location_by_id(
    salesperson_id: int,
    user,
) -> Optional[SalesPersonLocation]:
    """
    Retrieves the SalesPersonLocation for a given salesperson user ID,
    scoped to the requesting user's permissions.
    """
    return (
        get_salesperson_locations_qs(user=user)
        .filter(salesperson_id=salesperson_id)
        .first()
    )


def get_salesperson_location_history_qs(
    salesperson_id: int,
    user,
    start_datetime=None,
    end_datetime=None,
) -> QuerySet[SalesPersonLocationHistory]:
    """
    Returns historical GPS breadcrumb records for a given salesperson.
    Ensures the requesting user has permission to inspect this salesperson.
    """
    # Permission verification
    if getattr(user, "role", None) in ["Offline_SalesPerson", "SalesPerson"]:
        if user.id != salesperson_id:
            return SalesPersonLocationHistory.objects.none()
    elif getattr(user, "role", None) == "Franchise":
        location = SalesPersonLocation.objects.filter(
            salesperson_id=salesperson_id, salesperson__franchise_id=user.franchise_id
        ).first()
        if not location:
            return SalesPersonLocationHistory.objects.none()
    elif getattr(user, "role", None) == "Distributor":
        location = SalesPersonLocation.objects.filter(
            Q(
                salesperson_id=salesperson_id,
                salesperson__distributor_id=user.distributor_id,
            )
            | Q(
                salesperson_id=salesperson_id,
                salesperson__franchise__distributor_id=user.distributor_id,
            )
        ).first()
        if not location:
            return SalesPersonLocationHistory.objects.none()
    elif not (
        getattr(user, "is_superuser", False)
        or getattr(user, "role", None) == "SuperAdmin"
    ):
        return SalesPersonLocationHistory.objects.none()

    qs = (
        SalesPersonLocationHistory.objects
        .filter(salesperson_id=salesperson_id)
        .select_related("salesperson")
        .only(
            "id",
            "salesperson_id",
            "latitude",
            "longitude",
            "accuracy",
            "recorded_at",
            "created_at",
            "salesperson__username",
        )
        .order_by("-created_at")
    )

    if start_datetime:
        qs = qs.filter(created_at__gte=start_datetime)
    if end_datetime:
        qs = qs.filter(created_at__lte=end_datetime)

    return qs
