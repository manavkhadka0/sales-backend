from django.utils import timezone
from rest_framework import serializers

from offlineSales.models import Attendance, AttendanceConfig


def get_attendance_config() -> AttendanceConfig:
    """Return the singleton attendance configuration."""
    return AttendanceConfig.get_config()


def validate_attendance_window():
    """
    Raise a ValidationError if posting attendance is not allowed right now.
    Checks the cutoff time configured by the SuperAdmin.
    """
    config = get_attendance_config()

    now_local = timezone.localtime(timezone.now()).time()
    if now_local > config.cutoff_time:
        raise serializers.ValidationError(
            f"Attendance can only be posted before {config.cutoff_time.strftime('%I:%M %p')}. "
            f"Current time is {now_local.strftime('%I:%M %p')}."
        )


def create_attendance(
    sales_person,
    image=None,
    attendance_location=None,
    attendance_lat=None,
    attendance_long=None,
) -> Attendance:
    """
    Create an attendance record after validating the time window.
    Prevents duplicate attendance for the same day.
    """
    validate_attendance_window()

    today = timezone.localdate()
    if Attendance.objects.filter(
        sales_person=sales_person, attendance_date=today
    ).exists():
        raise serializers.ValidationError(
            "Attendance has already been posted for today."
        )

    return Attendance.objects.create(
        sales_person=sales_person,
        image=image,
        attendance_date=today,
        attendance_time=timezone.now(),
        attendance_location=attendance_location,
        attendance_lat=attendance_lat,
        attendance_long=attendance_long,
    )


def update_attendance_config(config: AttendanceConfig, validated_data: dict, user) -> AttendanceConfig:
    """Update the attendance configuration fields."""
    for field, value in validated_data.items():
        setattr(config, field, value)
    config.updated_by = user
    config.save()
    return config
