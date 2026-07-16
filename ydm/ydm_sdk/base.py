import requests

from .exceptions import YDMApiError, YDMValidationError


class BaseYDMClient:
    """Base client containing common configuration and HTTP request logic."""

    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {}
        if self.api_key:
            self.headers["X-API-KEY"] = self.api_key
        self.headers["Accept"] = "application/json"

    def _get_url(self, path: str) -> str:
        return f"{self.base_url}/api/{path.lstrip('/')}"

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        merged_headers = {**self.headers, **headers}

        try:
            response = requests.request(method, url, headers=merged_headers, **kwargs)
            if response.status_code >= 400:
                try:
                    err_detail = response.json()
                except Exception:
                    err_detail = response.text

                if response.status_code == 400:
                    raise YDMValidationError(
                        f"Validation Error: {err_detail}",
                        status_code=response.status_code,
                        response_text=response.text,
                    )
                else:
                    raise YDMApiError(
                        f"API Error ({response.status_code}): {err_detail}",
                        status_code=response.status_code,
                        response_text=response.text,
                    )
            return response
        except requests.RequestException as e:
            raise YDMApiError(f"HTTP Request failed: {e}")
