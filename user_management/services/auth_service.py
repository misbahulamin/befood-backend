from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify
from rest_framework.authtoken.models import Token

from .pending_registration import send_pending_activation_email, upsert_pending_registration
from .profile_onboarding import get_onboarding_completion
from user_management.validators import format_bd_phone_e164


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


def get_login_response(user):
    token, _ = Token.objects.get_or_create(user=user)
    profile = user.customer_profile
    from user_management.services.location_preference import get_location_confirmation_summary

    return {
        'token': token.key,
        'user': {'id': user.id, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name},
        'groups': list(user.groups.values_list('name', flat=True)),
        'customer_profile': {
            'phone': format_bd_phone_e164(profile.phone),
            'occupation': profile.occupation,
            'is_bachelor': profile.is_bachelor,
            'is_email_verified': profile.is_email_verified,
        },
        'onboarding_completion': get_onboarding_completion(user, profile),
        'location_confirmation': get_location_confirmation_summary(profile),
    }


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
