import os

import requests


def create_pickndrop_order(order, pickndrop):
    """
    Create and send an order to Pick n Drop API.

    Args:
        order: Order instance
        pickndrop: PickNDrop instance with API credentials

    Returns:
        dict: API response from Frappe
    """

    base_url = os.getenv("PICKNDROP_BASE_URL")
    endpoint = f"{base_url}/api/method/logi360.api.create_order"

    client_key = pickndrop.client_key
    client_secret = pickndrop.client_secret
    print(client_key, client_secret)

    headers = {
        "Authorization": f"token {client_key}:{client_secret}",
        "Content-Type": "application/json",
    }

    # ------------------------------
    # Build order description
    # ------------------------------
    order_items = order.order_products.all()

    if order_items.exists():
        order_description = ", ".join(
            [f"{item.product.product.name} x {item.quantity}" for item in order_items]
        )
    else:
        order_description = order.order_code

    # ------------------------------
    # Calculate COD Amount
    # ------------------------------
    product_price = float(order.total_amount)

    if order.prepaid_amount:
        product_price -= float(order.prepaid_amount)

    payload = {
        "codAmount": product_price,
        "orderDescription": order_description,
        "customerName": order.full_name,
        "primaryMobileNo": order.phone_number,
        "secondaryMobileNo": order.alternate_phone_number or "",
        "landmark": order.landmark if order.landmark else order.delivery_address,
        "destinationBranch": order.location.name.upper()
        if order.location
        else "KATHMANDU",
        "instruction": order.remarks or "",
        "destinationCityArea": order.delivery_address,
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        data = response.json()

        # ------------------------------
        # HANDLE FAILURE RESPONSE (400)
        # ------------------------------
        if response.status_code == 400 or data.get("success") is False:
            return {
                "status": "error",
                "error_code": data.get("error_code"),
                "message": data.get("message"),
                "data": data.get("data", {}),
            }

        # ------------------------------
        # HANDLE SUCCESS RESPONSE (200)
        # ------------------------------
        message = data.get("message", {})
        if message.get("status") == "success":
            delivery_data = message.get("data", {})
            tracking_url = delivery_data.get("tracking_url")
            tracking_code = None

            if tracking_url:
                tracking_code = tracking_url.rstrip("/").split("/")[-1]

            # SAVE LOGISTICS + TRACKING CODE
            order.logistics = "PicknDrop"
            order.tracking_code = tracking_code
            order.order_status = "Sent to PicknDrop"
            order.save(update_fields=["logistics", "tracking_code", "order_status"])

            return {
                "status": "success",
                "message": message.get("message"),
                "tracking_code": tracking_code,
                "pickup_order_id": delivery_data.get("orderID"),
                "tracking_url": delivery_data.get("tracking_url"),
            }

        # Unexpected format → treat as error
        return {
            "status": "error",
            "message": "Unexpected response format from PickNDrop",
            "response": data,
        }

    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}
