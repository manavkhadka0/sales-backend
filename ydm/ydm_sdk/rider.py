from typing import List, Dict, Any


class RiderAPI:
    """Rider related API methods."""

    def get_rider_commissions(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Retrieve rider commissions list."""
        url = self._get_url("rider/commissions/")
        response = self._request("GET", url, params=params)
        return response.json()

    def get_rider_commission_stats(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get rider commission summary stats."""
        url = self._get_url("rider/commissions/stats/")
        response = self._request("GET", url, params=params)
        return response.json()

    def get_rider_package_stats(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get package outcome stats (assigned, delivered, cancelled)."""
        url = self._get_url("rider/packages/stats/")
        response = self._request("GET", url, params=params)
        return response.json()

    def list_rider_orders(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """List and search orders assigned to a rider."""
        url = self._get_url("rider/orders/")
        response = self._request("GET", url, params=params)
        return response.json()

    def get_rider_payouts(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Retrieve payout history for riders."""
        url = self._get_url("rider/payouts/")
        response = self._request("GET", url, params=params)
        return response.json()

    def list_rider_commission_rates(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """List set commission rate rules."""
        url = self._get_url("rider/commission-rates/")
        response = self._request("GET", url, params=params)
        return response.json()

    def create_rider_commission_rate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new commission rate rule."""
        url = self._get_url("rider/commission-rates/")
        response = self._request("POST", url, json=data)
        return response.json()

    def get_rider_commission_rate(self, pk: int) -> Dict[str, Any]:
        """Retrieve details of a commission rate rule."""
        url = self._get_url(f"rider/commission-rates/{pk}/")
        response = self._request("GET", url)
        return response.json()

    def update_rider_commission_rate(self, pk: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update commission rate rule."""
        url = self._get_url(f"rider/commission-rates/{pk}/")
        response = self._request("PATCH", url, json=data)
        return response.json()

    def delete_rider_commission_rate(self, pk: int) -> None:
        """Delete commission rate rule."""
        url = self._get_url(f"rider/commission-rates/{pk}/")
        self._request("DELETE", url)

    def get_rider_daily_stats(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get rider performance history sorted daily."""
        url = self._get_url("rider/daily-stats/")
        response = self._request("GET", url, params=params)
        return response.json()

    def verify_rider_order(self, tracking_number: str, delivery_location_type: str) -> Dict[str, Any]:
        """Verify delivery type and mark rider verification step."""
        url = self._get_url(f"rider/orders/{tracking_number}/verify/")
        payload = {"delivery_location_type": delivery_location_type}
        response = self._request("POST", url, json=payload)
        return response.json()

    def update_rider_order_status(self, tracking_number: str, status_value: str, comment: str = None) -> Dict[str, Any]:
        """Update rider order status (ON_HOLD, DELIVERED, RESCHEDULED, CANCELLED)."""
        url = self._get_url(f"rider/orders/{tracking_number}/update-status/")
        payload = {"status": status_value}
        if comment:
            payload["comment"] = comment
        response = self._request("POST", url, json=payload)
        return response.json()
