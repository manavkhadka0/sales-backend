import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from tracking.models import SalesPersonLocation, SalesPersonLocationHistory

logger = logging.getLogger(__name__)

# Threshold for ignoring mobile GPS micro-jitter (0.00005 degrees ~ 5.5 meters)
GPS_JITTER_THRESHOLD = 0.00005


def update_salesperson_location(
    salesperson,
    latitude: float,
    longitude: float,
    accuracy: Optional[float] = None,
    recorded_at: Optional[Any] = None,
    save_history: bool = True,
) -> Tuple[SalesPersonLocation, bool]:
    """
    Updates or creates a SalesPersonLocation record for an offline salesperson.
    Marks salesperson as online and in the field.
    Creates a historical breadcrumb entry if movement exceeds jitter threshold.
    """
    role = getattr(salesperson, "role", None)
    if role not in ["Offline_SalesPerson", "SalesPerson"]:
        logger.warning(
            f"Attempted location update for invalid role user #{salesperson.id} ({salesperson.username}, Role: {role})"
        )
        raise ValueError(
            f"User #{salesperson.id} is not an authorized salesperson (Role: {role})."
        )

    location, created = SalesPersonLocation.objects.get_or_create(
        salesperson=salesperson,
        defaults={
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "is_online": True,
        },
    )

    if not created:
        location.latitude = latitude
        location.longitude = longitude
        location.accuracy = accuracy
        location.is_online = True
        location.save(
            update_fields=[
                "latitude",
                "longitude",
                "accuracy",
                "is_online",
                "last_updated_at",
            ]
        )

    # Breadcrumb recording with micro-jitter filtering
    if save_history:
        recent_history = (
            SalesPersonLocationHistory.objects
            .filter(salesperson=salesperson)
            .only("latitude", "longitude")
            .first()
        )
        is_same_spot = (
            recent_history is not None
            and math.isclose(
                recent_history.latitude, latitude, abs_tol=GPS_JITTER_THRESHOLD
            )
            and math.isclose(
                recent_history.longitude, longitude, abs_tol=GPS_JITTER_THRESHOLD
            )
        )
        if not is_same_spot:
            SalesPersonLocationHistory.objects.create(
                salesperson=salesperson,
                latitude=latitude,
                longitude=longitude,
                accuracy=accuracy,
                recorded_at=recorded_at or timezone.now(),
            )

    return location, created


def toggle_salesperson_online_status(
    salesperson,
    is_online: bool,
) -> SalesPersonLocation:
    """
    Toggles the online/offline field availability of a salesperson (shift check-in / check-out).
    """
    role = getattr(salesperson, "role", None)
    if role not in ["Offline_SalesPerson", "SalesPerson"]:
        raise ValueError(
            f"User #{salesperson.id} is not an authorized salesperson (Role: {role})."
        )

    location, _ = SalesPersonLocation.objects.get_or_create(
        salesperson=salesperson,
        defaults={
            "latitude": 0.0,
            "longitude": 0.0,
            "is_online": is_online,
        },
    )
    location.is_online = is_online
    location.save(update_fields=["is_online", "last_updated_at"])
    return location


def bulk_record_offline_pings(
    salesperson,
    pings: List[Dict[str, Any]],
) -> int:
    """
    Processes batch-buffered GPS pings uploaded by mobile app after reconnecting from offline areas.
    Inserts all historical breadcrumbs in bulk and updates latest SalesPersonLocation.
    """
    role = getattr(salesperson, "role", None)
    if role not in ["Offline_SalesPerson", "SalesPerson"]:
        raise ValueError(
            f"User #{salesperson.id} is not an authorized salesperson (Role: {role})."
        )

    if not pings:
        return 0

    history_objects = []
    latest_ping = pings[-1]

    for item in pings:
        lat = item.get("latitude")
        lng = item.get("longitude")
        if lat is None or lng is None:
            continue
        history_objects.append(
            SalesPersonLocationHistory(
                salesperson=salesperson,
                latitude=float(lat),
                longitude=float(lng),
                accuracy=item.get("accuracy"),
                recorded_at=item.get("recorded_at") or timezone.now(),
            )
        )

    if history_objects:
        SalesPersonLocationHistory.objects.bulk_create(history_objects, batch_size=500)

    # Update latest live location to the final ping in the batch
    if latest_ping:
        update_salesperson_location(
            salesperson=salesperson,
            latitude=float(latest_ping["latitude"]),
            longitude=float(latest_ping["longitude"]),
            accuracy=latest_ping.get("accuracy"),
            recorded_at=latest_ping.get("recorded_at"),
            save_history=False,
        )

    return len(history_objects)
