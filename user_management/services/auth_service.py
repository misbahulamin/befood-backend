from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify
from rest_framework.authtoken.models import Token

from .auth_session import build_customer_auth_response
from .pending_registration import send_pending_activation_email, upsert_pending_registration


def build_username(email):
    base = slugify(email.split('@')[0]) or 'customer'
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        counter += 1
        username = f'{base}-{counter}'
    return username


@transaction.atomic
def register_customer(validated_data, request):
    """
    Store a pending registration and send verification email.

    No permanent User/CustomerProfile is created until email verification succeeds.
    Returns (pending, None) for call-site compatibility with (user, profile).
    """
    data = dict(validated_data)
    pending = upsert_pending_registration(data)
    send_pending_activation_email(request, pending)
    return pending, None


def get_login_response(
    user,
    *,
    device_token=None,
    platform=None,
    user_agent='',
    auth_provider='email',
):
    """Unified customer auth success response (email login and shared callers)."""
    return build_customer_auth_response(
        user,
        auth_provider=auth_provider,
        device_token=device_token,
        platform=platform,
        user_agent=user_agent,
    )


def get_admin_login_response(user):
    token, _ = Token.objects.get_or_create(user=user)
    admin_profile = getattr(user, 'admin_profile', None)
    response = {
        'token': token.key,
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_superuser': user.is_superuser,
        },
        'groups': list(user.groups.values_list('name', flat=True)),
        'is_admin': True,
    }
    if admin_profile is not None:
        response['admin_profile'] = {
            'is_verified': admin_profile.is_verified,
            'verified_at': admin_profile.verified_at,
        }
    return response
