from django.contrib.auth.models import User


def is_verified_admin(user: User) -> bool:
    """
    Return True when the user is an active verified admin account.
    """
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    admin_profile = getattr(user, 'admin_profile', None)
    if admin_profile is None or not admin_profile.is_verified:
        return False
    return user.groups.filter(name='ADMIN').exists()
