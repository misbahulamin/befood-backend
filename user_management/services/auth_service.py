from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.text import slugify
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError

from ..models import CustomerProfile
from .email_verification import send_activation_email


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
    password = validated_data.pop('password')
    email = validated_data['email'].lower()
    user = User(
        username=build_username(email),
        email=email,
        first_name=validated_data['first_name'],
        last_name=validated_data['last_name'],
        is_active=False,
    )
    user.set_password(password)
    user.full_clean(exclude=['password'])
    user.save()
    profile = CustomerProfile.objects.create(
        user=user,
        phone=validated_data['phone'],
        occupation=validated_data['occupation'],
        is_bachelor=validated_data['is_bachelor'],
    )
    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)
    send_activation_email(request, user)
    return user, profile


def get_login_response(user):
    token, _ = Token.objects.get_or_create(user=user)
    profile = user.customer_profile
    return {
        'token': token.key,
        'user': {'id': user.id, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name},
        'groups': list(user.groups.values_list('name', flat=True)),
        'customer_profile': {
            'phone': profile.phone,
            'occupation': profile.occupation,
            'is_bachelor': profile.is_bachelor,
            'is_email_verified': profile.is_email_verified,
        },
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
