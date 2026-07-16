from typing import Any, Dict, List


class DashboardAPI:
    """Dashboard related API methods."""

    def get_dashboard_stats(self, user_id: Any = None) -> Dict[str, Any]:
        """Get standard order counts and amounts grouped by status."""
        url = self._get_url("dashboard/")
        params = {"user_id": user_id} if user_id else None
        response = self._request("GET", url, params=params)
        return response.json()

    def get_complete_dashboard_stats(self, user_id: Any = None) -> Dict[str, Any]:
        """Get overall metrics, performance, and daily aggregates."""
        url = self._get_url("dashboard/complete/")
        params = {"user_id": user_id} if user_id else None
        response = self._request("GET", url, params=params)
        return response.json()

    def get_daily_placed_stats(
        self, params: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Get daily placed order statistics. Accepts user_id, filter, start_date, end_date."""
        url = self._get_url("dashboard/daily/placed/")
        response = self._request("GET", url, params=params)
        return response.json()

    def get_daily_delivered_stats(
        self, params: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Get daily delivered order statistics. Accepts user_id, filter, start_date, end_date."""
        url = self._get_url("dashboard/daily/delivered/")
        response = self._request("GET", url, params=params)
        return response.json()

    def get_user_statement(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Retrieve user ledger/statement history. Accepts user_id, start_date, end_date."""
        url = self._get_url("user/statement/")
        response = self._request("GET", url, params=params)
        return response.json()
