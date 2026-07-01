import csv
import io

from django.db import transaction

from daraz.models import DarazLocation


def import_locations_from_csv(file_obj) -> int:
    """
    Parses a CSV file and imports/updates Daraz locations.
    Returns the count of successfully processed locations.
    """
    # Decode with utf-8-sig to automatically handle and strip UTF-8 BOM if present
    content = file_obj.read().decode("utf-8-sig")
    csv_file = io.StringIO(content)
    reader = csv.DictReader(csv_file)

    # Clean the header names to prevent leading/trailing whitespace
    if reader.fieldnames:
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
    else:
        reader.fieldnames = []

    locations_to_create = []
    seen_l4_ids = set()

    for row in reader:
        # Standardize matching both capitalized and lowercase header variations
        city = row.get("City") or row.get("city")
        l3_id = (
            row.get("L3 ID") or row.get("l3_id") or row.get("L3Id") or row.get("l3id")
        )
        area = row.get("Area") or row.get("area")
        l4_id = (
            row.get("L4 ID") or row.get("l4_id") or row.get("L4Id") or row.get("l4id")
        )

        if not city or not area or not l4_id:
            continue

        city = city.strip()
        l3_id = l3_id.strip() if l3_id else ""
        area = area.strip()
        l4_id = l4_id.strip()

        # Avoid duplicates within the CSV list itself
        if l4_id in seen_l4_ids:
            continue
        seen_l4_ids.add(l4_id)

        locations_to_create.append(
            DarazLocation(city=city, l3_id=l3_id, area=area, l4_id=l4_id)
        )

    if not locations_to_create:
        return 0

    with transaction.atomic():
        # Django bulk_create with update_conflicts handles inserting new and updating existing entries efficiently
        DarazLocation.objects.bulk_create(
            locations_to_create,
            update_conflicts=True,
            update_fields=["city", "l3_id", "area"],
            unique_fields=["l4_id"],
        )

    return len(locations_to_create)
