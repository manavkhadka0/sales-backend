from django.core.management.base import BaseCommand
from sales.models import Order


class Command(BaseCommand):
    help = "Update Order payment_screenshot paths to ensure they include payment_screenshots/ prefix"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without saving changes to the database",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write("Fetching orders with non-empty payment screenshots...")
        orders = Order.objects.exclude(payment_screenshot="").exclude(
            payment_screenshot__isnull=True
        )

        updated_count = 0
        skipped_count = 0

        for order in orders:
            old_path = str(order.payment_screenshot).strip()

            if not old_path:
                continue

            # Check if it already starts with payment_screenshots/
            if old_path.startswith("payment_screenshots/"):
                skipped_count += 1
                continue

            # Strip any legacy or full-URL prefixes
            clean_path = old_path
            prefixes_to_strip = [
                "https://sgp1.digitaloceanspaces.com/himalayancrm/public/yachuSales/",
                "public/yachuSales/",
                "yachuSales/",
                "media/",
                "public/",
            ]

            for prefix in prefixes_to_strip:
                if clean_path.startswith(prefix):
                    clean_path = clean_path[len(prefix) :]

            # Clean any nested payment_screenshots/ if present
            if clean_path.startswith("payment_screenshots/"):
                filename = clean_path[len("payment_screenshots/") :]
            else:
                filename = clean_path

            # Construct new path
            new_path = f"payment_screenshots/{filename}"

            self.stdout.write(
                f"Order ID {order.id} ({order.order_code}): '{old_path}' -> '{new_path}'"
            )
            updated_count += 1

            if not dry_run:
                order.payment_screenshot = new_path
                order.save(update_fields=["payment_screenshot"])

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Would update {updated_count} order(s). {skipped_count} already correctly formatted."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully updated {updated_count} order(s). {skipped_count} already correctly formatted."
                )
            )
