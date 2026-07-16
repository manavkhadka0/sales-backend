import io
from typing import Any, BinaryIO, Dict, List, Union


class LogisticsAPI:
    """Logistics related API methods."""

    def list_orders(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """List and filter orders. Accepts OrderFilter query parameters."""
        url = self._get_url("orders/")
        response = self._request("GET", url, params=params)
        return response.json()

    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single order."""
        url = self._get_url("orders/")
        response = self._request("POST", url, json=order_data)
        return response.json()

    def get_order(self, tracking_number: str) -> Dict[str, Any]:
        """Retrieve order details by tracking number."""
        url = self._get_url(f"orders/{tracking_number}/")
        response = self._request("GET", url)
        return response.json()

    def update_order_status(
        self, tracking_number: str, status_value: str
    ) -> Dict[str, Any]:
        """Update the status of an order."""
        url = self._get_url(f"orders/{tracking_number}/update-status/")
        response = self._request("POST", url, json={"status": status_value})
        return response.json()

    def list_comments(self, tracking_number: str) -> List[Dict[str, Any]]:
        """List comments of an order."""
        url = self._get_url(f"orders/{tracking_number}/comments/")
        response = self._request("GET", url)
        return response.json()

    def add_comment(self, tracking_number: str, message: str) -> Dict[str, Any]:
        """Add a comment to an order."""
        url = self._get_url(f"orders/{tracking_number}/comments/")
        response = self._request("POST", url, json={"message": message})
        return response.json()

    def download_template(self) -> bytes:
        """Download the Excel template for order imports."""
        url = self._get_url("orders/template/")
        response = self._request("GET", url)
        return response.content

    def import_orders(
        self, file_content: Union[bytes, BinaryIO], filename: str = "orders.xlsx"
    ) -> Dict[str, Any]:
        """Upload and import an Excel sheet containing orders."""
        url = self._get_url("orders/import/")
        if isinstance(file_content, bytes):
            file_obj = io.BytesIO(file_content)
        else:
            file_obj = file_content

        files = {
            "file": (
                filename,
                file_obj,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        response = self._request("POST", url, files=files)
        return response.json()

    def export_orders(
        self, order_ids: List[int] = None, filters: Dict[str, Any] = None
    ) -> bytes:
        """Export filtered orders to Excel sheet."""
        url = self._get_url("orders/export/")
        payload = {}
        if order_ids:
            payload["order_ids"] = order_ids
        if filters:
            payload.update(filters)

        response = self._request("POST", url, json=payload)
        return response.content
