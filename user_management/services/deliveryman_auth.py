from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError

from ..models import RiderProfile
from .deliveryman_email import (
    send_deliveryman_activation_email,
    send_deliveryman_approval_email,
    send_deliveryman_rejection_email,
)


DELIVERY_MAN_GROUP = 'DELIVERY_MAN'


def build_deliveryman_username(email):
    base = slugify(email.split('@')[0]) or 'deliveryman'
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        counter += 1
        username = f'{base}-{counter}'
    return username


@transaction.atomic
def register_deliveryman(validated_data, request):
    password = validated_data.pop('password')
    email = validated_data['email'].lower()
    user = User(
        username=build_deliveryman_username(email),
        email=email,
        first_name=validated_data['first_name'],
        last_name=validated_data['last_name'],
        is_active=False,
    )
    user.set_password(password)
    user.full_clean(exclude=['password'])
    user.save()
    profile = RiderProfile.objects.create(
        user=user,
        phone=validated_data['phone'],
        address=validated_data.get('address', ''),
        vehicle_type=validated_data.get('vehicle_type', ''),
        license_number=validated_data.get('license_number', ''),
        is_email_verified=False,
        approval_status=RiderProfile.ApprovalStatus.PENDING,
        is_verified=False,
    )
    group, _ = Group.objects.get_or_create(name=DELIVERY_MAN_GROUP)
    user.groups.add(group)
    send_deliveryman_activation_email(request, user)
    return user, profile


def get_deliveryman_login_response(user):
    token, _ = Token.objects.get_or_create(user=user)
    profile = user.rider_profile
    return {
        'token': token.key,
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        },
        'groups': list(user.groups.values_list('name', flat=True)),
        'rider_profile': {
            'public_id': str(profile.public_id),
            'phone': profile.phone,
            'address': profile.address,
            'vehicle_type': profile.vehicle_type,
            'license_number': profile.license_number,
            'is_email_verified': profile.is_email_verified,
            'approval_status': profile.approval_status,
            'is_verified': profile.is_verified,
            'is_available': profile.is_available,
        },
    }


def _require_email_verified(profile):
    if not profile.is_email_verified:
        raise ValidationError({'detail': 'Email must be verified before admin approval.'})


@transaction.atomic
def approve_deliveryman(profile, *, send_email=True):
    _require_email_verified(profile)
    now = timezone.now()
    profile.approval_status = RiderProfile.ApprovalStatus.APPROVED
    profile.is_verified = True
    profile.verified_at = now
    profile.rejected_at = None
    profile.rejection_reason = ''
    profile.save(
        update_fields=[
            'approval_status',
            'is_verified',
            'verified_at',
            'rejected_at',
            'rejection_reason',
            'updated_at',
        ]
    )
    user = profile.user
    user.is_active = True
    user.save(update_fields=['is_active'])
    group, _ = Group.objects.get_or_create(name=DELIVERY_MAN_GROUP)
    user.groups.add(group)
    if send_email:
        send_deliveryman_approval_email(user)
    return profile


@transaction.atomic
def reject_deliveryman(profile, reason='', *, send_email=True):
    now = timezone.now()
    profile.approval_status = RiderProfile.ApprovalStatus.REJECTED
    profile.is_verified = False
    profile.verified_at = None
    profile.rejected_at = now
    profile.rejection_reason = reason or ''
    profile.save(
        update_fields=[
            'approval_status',
            'is_verified',
            'verified_at',
            'rejected_at',
            'rejection_reason',
            'updated_at',
        ]
    )
    user = profile.user
    user.is_active = False
    user.save(update_fields=['is_active'])
    if send_email:
        send_deliveryman_rejection_email(user, reason=profile.rejection_reason)
    return profile


@transaction.atomic
def set_deliveryman_verified(profile, is_verified, *, admin_notes=None, send_email=True):
    """Operational verified-status management (approve or revoke)."""
    if is_verified:
        if admin_notes is not None:
            profile.admin_notes = admin_notes
            profile.save(update_fields=['admin_notes', 'updated_at'])
        return approve_deliveryman(profile, send_email=send_email)

    profile.approval_status = RiderProfile.ApprovalStatus.PENDING
    profile.is_verified = False
    profile.verified_at = None
    update_fields = ['approval_status', 'is_verified', 'verified_at', 'updated_at']
    if admin_notes is not None:
        profile.admin_notes = admin_notes
        update_fields.append('admin_notes')
    profile.save(update_fields=update_fields)
    user = profile.user
    user.is_active = False
    user.save(update_fields=['is_active'])
    return profile
