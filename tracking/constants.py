"""
Constants for the tracking application.
"""

# Duration in minutes after which a salesperson without pings is considered INACTIVE (heartbeat timeout)
HEARTBEAT_TIMEOUT_MINUTES = 5
HEARTBEAT_TIMEOUT_SECONDS = 300


class TrackingStatus:
    ONLINE = "ONLINE"        # Shift active AND ping within last 5 minutes
    INACTIVE = "INACTIVE"    # Shift active BUT no ping for > 5 minutes (signal drop / phone dead)
    OFFLINE = "OFFLINE"      # Explicitly clocked out / shift ended

    CHOICES = [
        (ONLINE, "Online (Actively Broadcasting)"),
        (INACTIVE, "Inactive / Signal Lost"),
        (OFFLINE, "Offline (Shift Ended)"),
    ]
