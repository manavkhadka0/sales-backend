from typing import Any, Dict, List


class AccountAPI:
    """Account related API methods."""

    def register_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new user (Public)."""
        url = self._get_url("account/register/")
        response = self._request("POST", url, json=data)
        return response.json()

    def login_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate user credentials and receive access tokens (Public)."""
        url = self._get_url("account/login/")
        response = self._request("POST", url, json=data)
        return response.json()

    def list_api_keys(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """List active API keys for the authenticated account."""
        url = self._get_url("account/api-keys/")
        response = self._request("GET", url, params=params)
        return response.json()

    def generate_api_key(self, expires_in_days: int = None) -> Dict[str, Any]:
        """Generate a new API key."""
        url = self._get_url("account/api-keys/")
        payload = {"expires_in_days": expires_in_days} if expires_in_days else {}
        response = self._request("POST", url, json=payload)
        return response.json()

    def list_users(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """List all active system accounts (Admins only)."""
        url = self._get_url("account/users/")
        response = self._request("GET", url, params=params)
        return response.json()

    def list_vendors(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """List registered vendors and stats (Admins/YDM staff only)."""
        url = self._get_url("account/vendors/")
        response = self._request("GET", url, params=params)
        return response.json()
