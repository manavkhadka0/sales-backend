from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from account.utils import get_password_changed_time, get_password_fingerprint


class CustomJWTAuthentication(JWTAuthentication):
    """JWT Authentication class that validates tokens against the user's current password fingerprint.

    - For new tokens with `pass_hash`: Validates directly against current password fingerprint.
    - For legacy tokens (missing `pass_hash`): Allows them to function normally until a password
      change occurs (checked via token's `iat` timestamp vs `user_pwd_changed` timestamp).
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        token_pass_hash = validated_token.get("pass_hash")
        current_pass_hash = get_password_fingerprint(user.password)

        if token_pass_hash is not None:
            if token_pass_hash != current_pass_hash:
                raise AuthenticationFailed(
                    "Password has been changed. Please log in again.",
                    code="password_changed",
                )
        else:
            # Handle legacy tokens without `pass_hash` claim
            pwd_changed_at = get_password_changed_time(user.id)
            if pwd_changed_at is not None:
                token_iat = validated_token.get("iat")
                if token_iat is not None and token_iat < pwd_changed_at:
                    raise AuthenticationFailed(
                        "Password has been changed. Please log in again.",
                        code="password_changed",
                    )

        return user
