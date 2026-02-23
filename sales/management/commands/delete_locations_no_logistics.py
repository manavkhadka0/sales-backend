from django.core.management.base import BaseCommand
from django.db.models import Q

from sales.models import Location


class Command(BaseCommand):
    help = "Delete all locations with no logistics (null or blank)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many would be deleted without actually deleting them",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Filter for locations where logistics is null or an empty string
        queryset = Location.objects.filter(Q(logistics__isnull=True) | Q(logistics=""))
        count = queryset.count()

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[DRY RUN] Found {count} locations with no logistics."
                )
            )
            for loc in queryset:
                self.stdout.write(f" - {loc.name} (ID: {loc.id})")
        else:
            if count == 0:
                self.stdout.write(
                    self.style.WARNING("No locations found with no logistics.")
                )
                return

            self.stdout.write(f"Deleting {count} locations...")
            queryset.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Successfully deleted {count} locations.")
            )
