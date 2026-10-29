from offlineSales.models import Attendance


def get_attendance_queryset(user):
    """
    Returns the attendance queryset scoped to the requesting user's access level.

    - SuperAdmin / Distributor / Franchise supervisors → all records
      filtered by franchise if the user has one.
    - Salesperson → only their own records.
    """
    role = getattr(user, "role", None)
    is_supervisor = user.is_superuser or role in ["SuperAdmin", "Distributor", "Franchise"]

    qs = (
        Attendance.objects.select_related("sales_person")
        .only(
            "id",
            "sales_person__id",
            "sales_person__username",
            "sales_person__first_name",
            "sales_person__last_name",
            "image",
            "attendance_date",
            "attendance_time",
            "attendance_location",
            "attendance_lat",
            "attendance_long",
        )
    )

    if is_supervisor:
        franchise = getattr(user, "franchise", None)
        if franchise and role != "SuperAdmin" and not user.is_superuser:
            qs = qs.filter(sales_person__franchise=franchise)
        return qs

    return qs.filter(sales_person=user)
