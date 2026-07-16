YDM Logistics Python SDK - Quick Start Guide
=============================================

This directory (`ydm_sdk`) is a fully self-contained Python package that provides convenient, type-hinted access to the YDM Logistics API endpoints from external Python applications.

PREREQUISITES
-------------
The SDK relies on the `requests` library. Ensure it is installed in your target project:

    pip install requests

HOW TO INTEGRATE INTO ANOTHER PROJECT
-------------------------------------
1. Copy the entire `ydm_sdk/` directory into your project's root or source directory.
2. Import and initialize the client in your application code:

    from ydm_sdk import YDMClient, YDMApiError, YDMValidationError

    # Initialize the client
    client = YDMClient(
        base_url="http://your-ydm-server.com",
        api_key="your_api_key_here"
    )

CODE EXAMPLES
-------------

1. LOGISTICS (Orders, Templates, Imports/Exports)
------------------------------------------------
    # Create an order
    new_order = client.create_order({
        "recipient_name": "John Doe",
        "recipient_phone": "9800000000",
        "recipient_address": "Kathmandu, Nepal",
        "cod_amount": 1500.00,
        "delivery_charge": 150.00,
        "payment_type": "COD",
        "product": [{"name": "Item A", "quantity": 1}],
        "remarks": "Deliver after 4 PM"
    })
    print("Created Order Tracking:", new_order["tracking_number"])

    # Export specific orders to Excel
    excel_data = client.export_orders(order_ids=[1, 2, 3])
    with open("orders.xlsx", "wb") as f:
        f.write(excel_data)

    # Bulk Import orders via Excel
    with open("my_orders.xlsx", "rb") as f:
        result = client.import_orders(file_content=f.read())
        print("Import Results:", result)

2. DASHBOARD (Stats & User Ledger/Statements)
---------------------------------------------
    # Get standard dashboard status stats (optionally for a specific user ID)
    stats = client.get_dashboard_stats(user_id=12)
    print("Delivered count:", stats["order_status"][0]["nos"])

    # Get complete performance stats
    metrics = client.get_complete_dashboard_stats(user_id=12)

    # Retrieve financial ledger/statement
    statement = client.get_user_statement(params={
        "user_id": 12,
        "start_date": "2026-07-01",
        "end_date": "2026-07-15"
    })

3. INVOICES (Client Billing & Reports)
--------------------------------------
    # List invoices
    invoices = client.list_invoices()

    # Create invoice report (dispute/cancellation issue)
    report = client.create_invoice_report({
        "invoice": 5,
        "comment": "Client requests correction on delivery charge"
    })

4. RIDER (Assigning & Delivering Orders)
---------------------------------------
    # Verification step: set location type (e.g. Inside/Outside Ringroad)
    client.verify_rider_order(
        tracking_number="YDM-A1B2C3",
        delivery_location_type="Inside Ringroad"
    )

    # Status update: update status with mandatory cancellation/hold comments
    client.update_rider_order_status(
        tracking_number="YDM-A1B2C3",
        status_value="DELIVERED",
        comment="Delivered to recipient family member"
    )

5. ACCOUNT (Authentication & Users)
-----------------------------------
    # Authenticate credentials to obtain JWT Tokens
    tokens = client.login_user({
        "username": "vendor_account",
        "password": "securepassword"
    })
    print("Access Token:", tokens["access"])

    # Generate a new API Key expiring in 30 days
    new_key = client.generate_api_key(expires_in_days=30)
    print("New API Key:", new_key["key"])


ERROR HANDLING
--------------
The SDK raises customized exceptions for network errors, invalid arguments, or HTTP 400+ issues:

    try:
        client.verify_rider_order("YDM-INVALID", "Inside Ringroad")
    except YDMValidationError as e:
        print("Input validation failed:", e)
    except YDMApiError as e:
        print("API returned error status:", e.status_code)
