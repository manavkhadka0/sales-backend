from django.core.management.base import BaseCommand

from sales.models import Location


class Command(BaseCommand):
    help = "Set logistics field to DASH for all existing Location records"

    def handle(self, *args, **kwargs):
        updated_count = Location.objects.update(logistics="DASH")
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {updated_count} locations to DASH."
            )
        )
