import hashlib
import time

from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken


def get_password_fingerprint(password: str) -> str:
    """Generate a SHA-256 fingerprint from the user's password hash."""
    if not password:
        return ""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()[:16]


def mark_password_changed(user_id: int):
    """Record the timestamp when a user's password was changed."""
    cache.set(f"user_pwd_changed_{user_id}", time.time(), timeout=365 * 86400)


def get_password_changed_time(user_id: int):
    """Retrieve the timestamp when the user's password was changed, if any."""
    return cache.get(f"user_pwd_changed_{user_id}")


def get_tokens_for_user(user):
    """Generate SimpleJWT refresh and access tokens containing the user's password fingerprint."""
    refresh = RefreshToken.for_user(user)
    pwd_fp = get_password_fingerprint(user.password)
    refresh["pass_hash"] = pwd_fp
    refresh.access_token["pass_hash"] = pwd_fp
    return refresh
