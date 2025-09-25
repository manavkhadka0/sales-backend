from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, datetime
from sales.models import Order
from logistics.models import OrderChangeLog
from account.models import CustomUser


class Command(BaseCommand):
    help = 'Create missing OrderChangeLog entries for orders from a specific date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--franchise-id',
            type=int,
            default=1,
            help='Franchise ID to process (default: 1)'
        )
        parser.add_argument(
            '--date',
            type=str,
            default='2025-09-14',
            help='Date to process in YYYY-MM-DD format (default: 2025-09-14)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating logs'
        )

    def handle(self, *args, **options):
        franchise_id = options['franchise_id']
        target_date_str = options['date']
        dry_run = options['dry_run']

        # Parse the target date
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            self.stdout.write(
                self.style.ERROR(
                    f'Invalid date format: {target_date_str}. Use YYYY-MM-DD')
            )
            return

        self.stdout.write(
            f'Processing franchise_id={franchise_id} for date={target_date}')
        self.stdout.write(f'Dry run: {dry_run}')

        # Find orders from the target date
        orders = Order.objects.filter(
            franchise_id=franchise_id,
            logistics="YDM",
            created_at__date=target_date
        ).order_by('created_at')

        self.stdout.write(
            f'Found {orders.count()} orders for franchise {franchise_id} on {target_date}')

        if not orders.exists():
            self.stdout.write('No orders found for this date and franchise.')
            return

        # Get a system user for creating logs
        system_user = CustomUser.objects.filter(role="SuperAdmin").first()
        if not system_user:
            system_user = CustomUser.objects.first()

        logs_created = 0

        for order in orders:
            self.stdout.write(
                f'Processing Order {order.id} ({order.order_code}): {order.full_name}')

            # Check if "Sent to YDM" log exists
            sent_to_ydm_log = order.change_logs.filter(
                new_status="Sent to YDM").first()

            if not sent_to_ydm_log:
                self.stdout.write('  Creating "Sent to YDM" log')
                log_timestamp = order.created_at + \
                    timezone.timedelta(minutes=1)

                if not dry_run:
                    OrderChangeLog.objects.create(
                        order=order,
                        user=system_user,
                        old_status="Pending",
                        new_status="Sent to YDM",
                        comment="Auto-generated log for missing entry",
                        changed_at=log_timestamp
                    )
                logs_created += 1
            else:
                self.stdout.write('  "Sent to YDM" log already exists')

            # Check if "Delivered" log exists for delivered orders
            if order.order_status == "Delivered":
                delivered_log = order.change_logs.filter(
                    new_status="Delivered").first()

                if not delivered_log:
                    self.stdout.write('  Creating "Delivered" log')
                    log_timestamp = order.updated_at

                    if not dry_run:
                        OrderChangeLog.objects.create(
                            order=order,
                            user=system_user,
                            old_status="Sent to YDM",
                            new_status="Delivered",
                            comment="Auto-generated log for missing delivery entry",
                            changed_at=log_timestamp
                        )
                    logs_created += 1
                else:
                    self.stdout.write('  "Delivered" log already exists')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would create {logs_created} missing logs')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Created {logs_created} missing logs')
            )
