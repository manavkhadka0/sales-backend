# utils.py (or inside models.py if you prefer)
from .models import OrderChangeLog


def create_order_log(order, old_status, new_status, user=None, comment=None):
    """
    Create a log entry for an order status change.

    Args:
        order: Order instance
        old_status: previous status of the order
        new_status: new status of the order
        user: CustomUser instance who made the change
        comment: Optional comment
    """
    if old_status == new_status:
        return
    OrderChangeLog.objects.create(
        order=order,
        user=user,
        old_status=old_status,
        new_status=new_status,
        comment=comment
    )
