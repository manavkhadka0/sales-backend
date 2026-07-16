from typing import Any, Dict, List


class InvoiceAPI:
    """Invoice related API methods."""

    def list_invoices(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """List and filter invoices."""
        url = self._get_url("invoices/")
        response = self._request("GET", url, params=params)
        return response.json()

    def create_invoice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new invoice."""
        url = self._get_url("invoices/")
        response = self._request("POST", url, json=data)
        return response.json()

    def get_invoice(self, pk: int) -> Dict[str, Any]:
        """Retrieve invoice detail by ID."""
        url = self._get_url(f"invoices/{pk}/")
        response = self._request("GET", url)
        return response.json()

    def update_invoice(self, pk: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update/patch an invoice."""
        url = self._get_url(f"invoices/{pk}/")
        response = self._request("PATCH", url, json=data)
        return response.json()

    def delete_invoice(self, pk: int) -> None:
        """Delete an invoice."""
        url = self._get_url(f"invoices/{pk}/")
        self._request("DELETE", url)

    def list_invoice_reports(
        self, params: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """List all invoice issue/cancellation reports."""
        url = self._get_url("invoices/reports/")
        response = self._request("GET", url, params=params)
        return response.json()

    def create_invoice_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Report an invoice."""
        url = self._get_url("invoices/reports/")
        response = self._request("POST", url, json=data)
        return response.json()

    def get_invoice_report(self, pk: int) -> Dict[str, Any]:
        """Retrieve an invoice report detail."""
        url = self._get_url(f"invoices/reports/{pk}/")
        response = self._request("GET", url)
        return response.json()

    def update_invoice_report(self, pk: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update/patch an invoice report."""
        url = self._get_url(f"invoices/reports/{pk}/")
        response = self._request("PATCH", url, json=data)
        return response.json()

    def delete_invoice_report(self, pk: int) -> None:
        """Delete an invoice report."""
        url = self._get_url(f"invoices/reports/{pk}/")
        self._request("DELETE", url)
