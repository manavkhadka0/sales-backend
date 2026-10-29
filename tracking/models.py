from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from tracking.constants import HEARTBEAT_TIMEOUT_MINUTES, TrackingStatus


class SalesPersonLocation(models.Model):
    """
    Stores the current real-time GPS location and operational status of a field salesperson.
    """

    salesperson = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="salesperson_location",
        db_index=True,
    )
    latitude = models.FloatField(db_index=True)
    longitude = models.FloatField(db_index=True)
    accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS accuracy in meters",
    )
    is_online = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether the salesperson is currently active and in field.",
    )
    last_updated_at = models.DateTimeField(auto_now=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tracking_salesperson_location"
        verbose_name = "Sales Person Location"
        verbose_name_plural = "Sales Person Locations"
        indexes = [
            models.Index(fields=["is_online", "last_updated_at"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        status_str = self.tracking_status
        salesperson_name = getattr(
            self.salesperson, "username", str(self.salesperson_id)
        )
        return (
            f"{salesperson_name} - [{self.latitude}, {self.longitude}] ({status_str})"
        )

    @property
    def is_active_now(self) -> bool:
        """
        Returns True only if the salesperson is marked online AND has sent a ping
        within the last HEARTBEAT_TIMEOUT_MINUTES.
        """
        if not self.is_online or not self.last_updated_at:
            return False
        threshold = timezone.now() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)
        return self.last_updated_at >= threshold

    @property
    def tracking_status(self) -> str:
        """
        Computes real-time status:
        - OFFLINE: Shift ended / is_online is False
        - ONLINE: Shift active AND ping within last 5 minutes
        - INACTIVE: Shift active BUT no ping for > 5 minutes (phone dead / signal lost)
        """
        if not self.is_online:
            return TrackingStatus.OFFLINE
        return TrackingStatus.ONLINE if self.is_active_now else TrackingStatus.INACTIVE

    @property
    def seconds_since_last_ping(self) -> int:
        if not self.last_updated_at:
            return 0
        diff = timezone.now() - self.last_updated_at
        return max(0, int(diff.total_seconds()))


class SalesPersonLocationHistory(models.Model):
    """
    Breadcrumb trail of historical GPS coordinates for route playback, auditing, and analytics.
    """

    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="salesperson_location_history",
        db_index=True,
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text="GPS accuracy in meters",
    )
    recorded_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Device-recorded timestamp for offline sync",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tracking_salesperson_location_history"
        verbose_name = "Sales Person Location History"
        verbose_name_plural = "Sales Person Location Histories"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["salesperson", "created_at"]),
            models.Index(fields=["salesperson", "recorded_at"]),
        ]

    def __str__(self):
        salesperson_name = getattr(
            self.salesperson, "username", str(self.salesperson_id)
        )
        ts = self.recorded_at or self.created_at
        return f"History: {salesperson_name} @ {ts} [{self.latitude}, {self.longitude}]"
