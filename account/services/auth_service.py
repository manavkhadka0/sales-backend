from account.models import CustomUser
from account.utils import mark_password_changed


def change_user_password(user: CustomUser, new_password: str) -> CustomUser:
    """Update a user's password, record password change time, and save the instance.

    Saving the new password updates user.password and records the change timestamp,
    which automatically invalidates both new tokens and legacy JWT tokens across all devices.
    """
    user.set_password(new_password)
    user.save()
    mark_password_changed(user.id)
    return user
