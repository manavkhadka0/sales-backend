# Compatibility module mapping old tracking service to location service
from tracking.services.location_service import (
    bulk_record_offline_pings,
    toggle_salesperson_online_status,
    update_salesperson_location,
)

__all__ = [
    "update_salesperson_location",
    "toggle_salesperson_online_status",
    "bulk_record_offline_pings",
]
