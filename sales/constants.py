# sales/constants.py

# Statuses that are considered active/completed for statistics, revenue, and dashboards
ACTIVE_ORDER_STATUSES = [
    "Delivered",
    "Pending",
    "Indrive",
    "Sent to Dash",
    "Sent to YDM",
    "Sent to Daraz",
    "Sent to PicknDrop",
    "Processing",
]

# Statuses that are cancelled, returned, or pending return and thus excluded from sales/revenue
EXCLUDED_STATUSES = [
    "Cancelled",
    "Returned By Customer",
    "Returned By Dash",
    "Return Pending",
    "Returned By PicknDrop",
    "Returned By YDM",
    "Returned By Daraz",
]
