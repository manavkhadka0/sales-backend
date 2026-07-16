class YDMApiError(Exception):
    """Base exception class for YDM SDK errors."""
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class YDMValidationError(YDMApiError):
    """Raised when validation checks fail on the client-side or server-side."""
    pass
