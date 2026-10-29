from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from offlineSales.models import (
    OfflineCustomer,
    OfflineOrder,
    OfflineOrderItem,
    OfflinePaymentHistory,
)
from sales.models import Inventory, InventoryChangeLog


def create_offline_order(
    user,
    customer: OfflineCustomer,
    items_data: list,
    total_amount: Decimal = Decimal("0.00"),
    paid_amount: Decimal = Decimal("0.00"),
    payment_method: str = OfflinePaymentHistory.PaymentMethod.CASH,
    payment_screenshot=None,
    remarks: str = None,
    order_date=None,
    initial_payment_data: dict = None,
) -> OfflineOrder:
    """
    Creates an offline order atomically:
    1. Validates and deducts stock from sales.Inventory for the customer's franchise.
    2. Logs inventory deduction in InventoryChangeLog.
    3. Sets total_amount and paid_amount sent from frontend.
    4. Calculates remaining_amount (total_amount - paid_amount) and payment_status.
    5. Creates order and order items (inventory and quantity only).
    6. Records initial payment history if paid_amount > 0.
    """
    if not items_data:
        raise ValidationError({
            "items": "At least one product item is required to place an order."
        })

    franchise = customer.franchise
    if not franchise:
        raise ValidationError({
            "customer": "The selected customer is not linked to any franchise."
        })

    with transaction.atomic():
        items_to_create = []

        for item_data in items_data:
            inventory_id = item_data.get("inventory_id")
            quantity = item_data.get("quantity", 0)

            if quantity <= 0:
                raise ValidationError({
                    "items": f"Quantity must be greater than zero for inventory item {inventory_id}."
                })

            try:
                inventory = (
                    Inventory.objects
                    .select_for_update(of=("self",))
                    .select_related("product")
                    .get(id=inventory_id)
                )
            except Inventory.DoesNotExist:
                raise ValidationError({
                    "items": f"Inventory item with ID {inventory_id} does not exist."
                })

            if inventory.franchise_id != franchise.id:
                raise ValidationError({
                    "items": (
                        f"Inventory item '{inventory.product.name}' does not belong to the customer's franchise "
                        f"({franchise.name})."
                    )
                })

            if inventory.quantity < quantity:
                raise ValidationError({
                    "items": (
                        f"Insufficient stock for product '{inventory.product.name}'. "
                        f"Available: {inventory.quantity}, Requested: {quantity}."
                    )
                })

            # Deduct inventory stock
            old_qty = inventory.quantity
            inventory.quantity -= quantity
            inventory.save(update_fields=["quantity"])

            # Log stock deduction
            InventoryChangeLog.objects.create(
                inventory=inventory,
                user=user,
                old_quantity=old_qty,
                new_quantity=inventory.quantity,
                action="order_created",
            )

            items_to_create.append(
                OfflineOrderItem(
                    inventory=inventory,
                    quantity=quantity,
                )
            )

        # Parse and validate total_amount
        total_amt = (
            Decimal(str(total_amount)) if total_amount is not None else Decimal("0.00")
        )
        if total_amt < Decimal("0.00"):
            raise ValidationError({"total_amount": "Total amount cannot be negative."})

        # Parse and validate paid_amount (support both direct paid_amount and initial_payment payload)
        paid_amt = (
            Decimal(str(paid_amount)) if paid_amount is not None else Decimal("0.00")
        )
        if initial_payment_data and initial_payment_data.get("amount"):
            paid_amt = Decimal(str(initial_payment_data["amount"]))
            payment_method = (
                initial_payment_data.get("payment_method") or payment_method
            )
            payment_screenshot = (
                initial_payment_data.get("payment_screenshot") or payment_screenshot
            )
            if initial_payment_data.get("remarks"):
                remarks = initial_payment_data["remarks"]

        if paid_amt < Decimal("0.00"):
            raise ValidationError({"paid_amount": "Paid amount cannot be negative."})

        if paid_amt > total_amt:
            raise ValidationError({
                "paid_amount": (
                    f"Paid amount (Rs. {paid_amt}) cannot exceed the total order amount "
                    f"(Rs. {total_amt})."
                )
            })

        # Calculate remaining amount and payment status
        remaining_amt = max(Decimal("0.00"), total_amt - paid_amt)
        if remaining_amt == Decimal("0.00") and total_amt > Decimal("0.00"):
            payment_status = OfflineOrder.PaymentStatus.PAID
        elif paid_amt > Decimal("0.00"):
            payment_status = OfflineOrder.PaymentStatus.PARTIAL
        else:
            payment_status = OfflineOrder.PaymentStatus.UNPAID

        # Initialize and save OfflineOrder
        order = OfflineOrder(
            franchise=franchise,
            sales_person=user,
            customer=customer,
            order_date=order_date or timezone.localdate(),
            order_status=OfflineOrder.OrderStatus.DELIVERED,
            total_amount=total_amt,
            paid_amount=paid_amt,
            remaining_amount=remaining_amt,
            payment_status=payment_status,
            remarks=remarks,
        )
        order.save()

        # Record initial payment history if paid_amount was provided
        if paid_amt > Decimal("0.00"):
            OfflinePaymentHistory.objects.create(
                customer=customer,
                order=order,
                amount=paid_amt,
                payment_method=payment_method
                or OfflinePaymentHistory.PaymentMethod.CASH,
                payment_screenshot=payment_screenshot,
                remarks=remarks or "Initial payment at order placement",
                recorded_by=user,
            )

        # Link order and bulk create items
        for item in items_to_create:
            item.order = order
        OfflineOrderItem.objects.bulk_create(items_to_create)

        return order


def cancel_offline_order(order: OfflineOrder, user) -> OfflineOrder:
    """
    Cancels an offline order atomically and restores the deducted inventory stock.
    """
    with transaction.atomic():
        locked_order = (
            OfflineOrder.objects
            .select_for_update(of=("self",))
            .select_related("franchise")
            .get(id=order.id)
        )

        if locked_order.order_status == OfflineOrder.OrderStatus.CANCELLED:
            raise ValidationError("This order is already cancelled.")

        # Restore inventory
        order_items = locked_order.items.select_related(
            "inventory", "inventory__product"
        ).all()
        for item in order_items:
            inv = item.inventory
            old_qty = inv.quantity
            inv.quantity += item.quantity
            inv.save(update_fields=["quantity"])

            InventoryChangeLog.objects.create(
                inventory=inv,
                user=user,
                old_quantity=old_qty,
                new_quantity=inv.quantity,
                action="order_cancelled",
            )

        locked_order.order_status = OfflineOrder.OrderStatus.CANCELLED
        locked_order.remaining_amount = Decimal("0.00")
        locked_order.save(
            update_fields=["order_status", "remaining_amount", "updated_at"]
        )

        return locked_order


def update_offline_order(
    order: OfflineOrder, validated_data: dict, user
) -> OfflineOrder:
    """
    Updates an offline order. If order_status is changed to Cancelled,
    it automatically cancels the order and increases/restores the inventory stock.
    """
    new_status = validated_data.get("order_status")

    with transaction.atomic():
        locked_order = (
            OfflineOrder.objects
            .select_for_update(of=("self",))
            .select_related("franchise")
            .get(id=order.id)
        )

        # If transitioning to CANCELLED, restore inventory
        if new_status == OfflineOrder.OrderStatus.CANCELLED:
            if locked_order.order_status == OfflineOrder.OrderStatus.CANCELLED:
                raise ValidationError({
                    "order_status": "This order is already cancelled."
                })
            # Remove order_status from validated_data so cancel_offline_order handles it
            validated_data_copy = {
                k: v for k, v in validated_data.items() if k != "order_status"
            }
            for attr, value in validated_data_copy.items():
                setattr(locked_order, attr, value)
            locked_order.save()
            return cancel_offline_order(locked_order, user)

        # If order is already cancelled, prevent reopening
        if (
            locked_order.order_status == OfflineOrder.OrderStatus.CANCELLED
            and new_status
            and new_status != OfflineOrder.OrderStatus.CANCELLED
        ):
            raise ValidationError({
                "order_status": "Cannot change the status of a cancelled order. Its inventory has already been restored."
            })

        for attr, value in validated_data.items():
            setattr(locked_order, attr, value)

        locked_order.save()
        return locked_order
