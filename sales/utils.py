import json


def get_owner_by_role(user):
    """
    Determines inventory owner and field name based on user role.
    """
    if user.role == "SuperAdmin":
        return getattr(user, "factory", None), "factory"
    elif user.role == "Distributor":
        return getattr(user, "distributor", None), "distributor"
    elif user.role in ["Franchise", "SalesPerson", "Packaging"]:
        return getattr(user, "franchise", None), "franchise"
    return None, None


def get_inventory_by_user_role(user, product_id=None):
    """
    Returns a queryset of Inventory objects filtered by user's organization (factory/distributor/franchise).
    Optionally filters by product_id if provided.
    """
    from sales.models import Inventory

    owner, owner_field = get_owner_by_role(user)
    if owner and owner_field:
        filter_kwargs = {owner_field: owner}
        if product_id is not None:
            filter_kwargs["id"] = product_id
        return Inventory.objects.filter(**filter_kwargs)
    return Inventory.objects.none()


def format_inventory_list(inventory_queryset, filter_ready=False, include_status=True):
    """
    Formats inventory queryset consistently.
    """
    if filter_ready:
        inventory_queryset = inventory_queryset.filter(status="ready_to_dispatch")

    data = []
    for inventory in inventory_queryset:
        item = {
            "id": inventory.id,
            "product_id": inventory.product.id,
            "product": inventory.product.name,
            "quantity": inventory.quantity,
        }
        if include_status:
            item["status"] = inventory.status
        data.append(item)
    return data


def format_product_inventory_list(inventory_queryset, include_status=False):
    """
    Formats inventory data for ProductListView.
    """
    base_fields = {
        "id",
        "product",
        "product__id",
        "product__name",
        "quantity",
    }

    if include_status:
        base_fields.add("status")

    inventory_data = inventory_queryset.values(*base_fields)

    product_list = []
    for inv in inventory_data:
        product_dict = {
            "inventory_id": inv["id"],
            "product_id": inv["product__id"],
            "product_name": inv["product__name"],
            "quantity": inv["quantity"],
        }
        if include_status:
            product_dict["status"] = inv["status"]
        product_list.append(product_dict)

    return product_list


def append_order_status_comments(serializer_data, status_filter):
    """
    Appends status change comments to serializer data if status_filter is provided.
    """
    if not status_filter or not serializer_data:
        return serializer_data

    from logistics.models import OrderChangeLog

    order_ids = [order["id"] for order in serializer_data]
    logs = OrderChangeLog.objects.filter(
        order_id__in=order_ids, new_status__icontains=status_filter
    ).order_by("changed_at")
    latest_comments = {log.order_id: log.comment for log in logs}
    for order_data in serializer_data:
        order_data["status_change_comment"] = latest_comments.get(
            order_data["id"], None
        )
    return serializer_data


def parse_order_products(request_data):
    """
    Parses order_products from request data, handling both list and JSON string formats.
    Returns (order_products, error_response) tuple.
    """
    order_products = request_data.get("order_products")
    if isinstance(order_products, list):
        return order_products, None

    if hasattr(request_data, "getlist"):
        order_products_str = request_data.get("order_products")
        if order_products_str:
            try:
                return json.loads(order_products_str), None
            except json.JSONDecodeError:
                return None, {"error": "Invalid order_products format"}

    return None, None


def handle_free_delivery_toggle(order, new_is_delivery_free):
    """
    Toggles the is_delivery_free status of an order and adjusts the total amount by 100.
    """
    if new_is_delivery_free is None:
        return

    is_free = str(new_is_delivery_free).lower() in ["true", "1", "yes"]

    if is_free and not order.is_delivery_free:
        order.total_amount -= 100
    elif not is_free and order.is_delivery_free:
        order.total_amount += 100

    order.is_delivery_free = is_free


def resolve_order_logistics_and_status(logistics, order_status, current_status):
    """
    Resolves conflict or shortcuts between logistics and order_status.
    """
    resolved_logistics = logistics
    resolved_status = order_status

    if logistics == "YDM":
        resolved_status = "Sent to YDM"
    elif logistics == "DASH" and current_status == "Sent to YDM":
        resolved_status = "Pending"

    if order_status == "Sent to YDM":
        resolved_logistics = "YDM"
    elif order_status == "Sent to Dash":
        resolved_logistics = "DASH"
    elif order_status == "Sent to Daraz":
        resolved_logistics = "Daraz"
    elif order_status == "Sent to PicknDrop":
        resolved_logistics = "PicknDrop"

    return resolved_logistics, resolved_status


def restore_order_inventory(order, user):
    """
    Restores inventory for all products in an order (increases stock).
    """
    from sales.models import InventoryChangeLog

    for order_product in order.order_products.all():
        try:
            inv = order_product.product
            old_qty = inv.quantity
            inv.quantity += order_product.quantity
            inv.save()

            InventoryChangeLog.objects.create(
                inventory=inv,
                user=user,
                old_quantity=old_qty,
                new_quantity=inv.quantity,
                action="order_cancelled",
            )
        except Exception as e:
            print(f"Error restoring inventory: {e}")


def deduct_order_inventory(order, user):
    """
    Deducts inventory for all products in an order (decreases stock).
    Raises Exception if there is insufficient inventory.
    """
    from sales.models import InventoryChangeLog

    for order_product in order.order_products.all():
        inv = order_product.product
        old_qty = inv.quantity

        if inv.quantity < order_product.quantity:
            raise Exception(
                f"Insufficient inventory for {inv.product.name} to restore order."
            )

        inv.quantity -= order_product.quantity
        inv.save()

        InventoryChangeLog.objects.create(
            inventory=inv,
            user=user,
            old_quantity=old_qty,
            new_quantity=inv.quantity,
            action="order_created",
        )


def deduct_single_inventory_item(user, instance, inv_id, qty):
    """
    Deducts quantity from a specific inventory item based on user/instance context.
    """
    from sales.models import Inventory, InventoryChangeLog

    try:
        # Organizational lookup for inventory (priority: franchise > distributor > factory)
        if instance.franchise:
            inv = Inventory.objects.get(id=inv_id, franchise=instance.franchise)
        elif instance.distributor:
            inv = Inventory.objects.get(id=inv_id, distributor=instance.distributor)
        elif instance.factory:
            inv = Inventory.objects.get(id=inv_id, factory=instance.factory)
        else:
            inv = Inventory.objects.get(id=inv_id)

        old_qty = inv.quantity
        inv.quantity -= qty
        inv.save()

        InventoryChangeLog.objects.create(
            inventory=inv,
            user=user,
            old_quantity=old_qty,
            new_quantity=inv.quantity,
            action="order_created",
        )
    except Inventory.DoesNotExist:
        raise Exception(f"Inventory ID {inv_id} not found for this organization.")
