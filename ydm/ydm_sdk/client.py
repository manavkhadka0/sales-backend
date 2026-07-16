from .account import AccountAPI
from .base import BaseYDMClient
from .dashboard import DashboardAPI
from .invoice import InvoiceAPI
from .logistics import LogisticsAPI
from .rider import RiderAPI


class YDMClient(
    BaseYDMClient, LogisticsAPI, DashboardAPI, InvoiceAPI, RiderAPI, AccountAPI
):
    """
    Unified Python SDK client for YDM Logistics API.
    Combines Logistics, Dashboard, Invoice, Rider, and Account endpoints into a single client.
    """

    pass
