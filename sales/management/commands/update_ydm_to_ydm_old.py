from django.core.management.base import BaseCommand
from django.db import transaction
from sales.models import Order


class Command(BaseCommand):
    help = 'Update all orders where logistics is YDM to YDM_OLD'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without committing changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write("Fetching orders where logistics is 'YDM'...")
        orders_to_update = Order.objects.filter(logistics="YDM")
        count = orders_to_update.count()
        
        self.stdout.write(f"Found {count} orders to update.")
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No orders to update."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would update {count} orders from logistics='YDM' to logistics='YDM_OLD'."
                )
            )
            # Display a few order codes as preview
            preview_orders = orders_to_update[:10]
            self.stdout.write("Preview of orders that would be updated:")
            for o in preview_orders:
                self.stdout.write(f"  - Order ID: {o.id}, Order Code: {o.order_code}, Customer: {o.full_name}")
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more.")
        else:
            with transaction.atomic():
                updated_count = Order.objects.filter(logistics="YDM").update(logistics="YDM_OLD")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully updated {updated_count} orders from logistics='YDM' to logistics='YDM_OLD'."
                    )
                )
