#!/usr/bin/env python
"""
Test script to verify that the statement generation now includes data from 2025-09-14.
"""

from logistics.views import generate_order_tracking_statement_optimized, calculate_dashboard_pending_cod
from logistics.models import OrderChangeLog
from sales.models import Order
import os
import sys
import django
from datetime import datetime, date

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_backend.settings')
django.setup()


def test_statement_generation():
    """Test the statement generation for franchise 1 from 2025-09-14 to 2025-09-25."""
    print("Testing Statement Generation Fix")
    print("=" * 50)

    franchise_id = 1
    start_date = date(2025, 9, 14)
    end_date = date(2025, 9, 25)

    print(f"Testing franchise_id={franchise_id}")
    print(f"Date range: {start_date} to {end_date}")
    print("-" * 50)

    # Get dashboard data
    dashboard_data = calculate_dashboard_pending_cod(franchise_id)
    print("Dashboard Data:")
    for key, value in dashboard_data.items():
        print(f"  {key}: {value}")
    print()

    # Generate statement
    statement_data = generate_order_tracking_statement_optimized(
        franchise_id, start_date, end_date, dashboard_data
    )

    print(f"Statement generated with {len(statement_data)} days")
    print("-" * 50)

    # Check if 2025-09-14 is included
    sept_14_data = None
    for day_data in statement_data:
        if day_data['date'] == '2025-09-14':
            sept_14_data = day_data
            break

    if sept_14_data:
        print("✅ 2025-09-14 data found in statement:")
        for key, value in sept_14_data.items():
            print(f"  {key}: {value}")
    else:
        print("❌ 2025-09-14 data NOT found in statement")

    print("\nAll statement data:")
    for day_data in statement_data:
        print(f"{day_data['date']}: Orders={day_data['total_order']}, Amount={day_data['total_amount']}, Deliveries={day_data['delivery_count']}")


def check_orders_and_logs():
    """Check the actual orders and logs for 2025-09-14."""
    print("\nChecking Orders and Logs for 2025-09-14")
    print("=" * 50)

    franchise_id = 1
    target_date = date(2025, 9, 14)

    # Get orders for the date
    orders = Order.objects.filter(
        franchise_id=franchise_id,
        logistics="YDM",
        created_at__date=target_date
    )

    print(
        f"Found {orders.count()} orders for franchise {franchise_id} on {target_date}")

    for order in orders:
        print(f"\nOrder {order.id} ({order.order_code}):")
        print(f"  Customer: {order.full_name}")
        print(f"  Status: {order.order_status}")
        print(f"  Created: {order.created_at}")
        print(f"  Total Amount: {order.total_amount}")
        print(f"  Prepaid Amount: {order.prepaid_amount}")

        # Check logs
        logs = order.change_logs.all().order_by('changed_at')
        print(f"  Logs ({logs.count()}):")
        for log in logs:
            print(f"    {log.changed_at}: {log.old_status} → {log.new_status}")


def main():
    """Main test function."""
    print("Statement Generation Fix Test")
    print("=" * 60)

    # First check the raw data
    check_orders_and_logs()

    # Then test the statement generation
    test_statement_generation()


if __name__ == "__main__":
    main()
