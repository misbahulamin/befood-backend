"""Target user and device resolution for admin push campaigns."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.http import QueryDict
from rest_framework.exceptions import ValidationError

from notifications.models import NotificationPreference
from user_management.models import AdminProfile, CustomerProfile, DeviceToken, RiderProfile, StaffProfile
from user_management.services.admin_customer import apply_customer_list_filters, customer_base_queryset

PUSH_FILTER_ALLOWLIST = frozenset(
    {
        'is_active',
        'is_email_verified',
        'registered_from',
        'registered_to',
        'has_active_subscription',
        'has_wallet',
        'service_area_public_id',
    }
)

TARGET_TYPE_MAP = {
    'user': 'single_user',
    'users': 'selected_users',
    'filter': 'filtered_users',
    'all': 'all_users',
}


class InvalidTargetUsersError(ValidationError):
    def __init__(self, invalid_user_ids: list[int]):
        super().__init__(
            {
                'target': [
                    f'Invalid customer user ID(s): {", ".join(str(uid) for uid in sorted(invalid_user_ids))}.'
                ]
            }
        )


def normalize_target_config(target: dict) -> dict:
    target_type = (target or {}).get('type', '').strip()
    normalized = {'type': target_type}
    if target_type == 'user':
        normalized['user_id'] = target.get('user_id')
    elif target_type == 'users':
        normalized['user_ids'] = sorted(set(target.get('user_ids') or []))
    elif target_type == 'filter':
        normalized['filters'] = dict(sorted((target.get('filters') or {}).items()))
    elif target_type == 'all':
        normalized['confirm_broadcast'] = bool(target.get('confirm_broadcast', False))
    return normalized


def _customer_user_queryset() -> QuerySet[User]:
    return User.objects.filter(customer_profile__isnull=False).select_related('customer_profile')


def get_customer_user_ids(user_ids: list[int]) -> tuple[set[int], set[int]]:
    """Return (valid customer user ids, invalid ids)."""
    unique_ids = {int(uid) for uid in user_ids}
    if not unique_ids:
        return set(), set()

    customer_ids = set(
        CustomerProfile.objects.filter(user_id__in=unique_ids).values_list('user_id', flat=True)
    )
    invalid = unique_ids - customer_ids
    return customer_ids, invalid


def validate_customer_user_ids(user_ids: list[int]) -> None:
    _, invalid = get_customer_user_ids(user_ids)
    if invalid:
        raise InvalidTargetUsersError(sorted(invalid))


def _reject_non_customer_users(user_ids: list[int]) -> None:
    if not user_ids:
        return

    blocked = set(
        AdminProfile.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True)
    )
    blocked.update(
        RiderProfile.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True)
    )
    blocked.update(
        StaffProfile.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True)
    )
    _, non_customers = get_customer_user_ids(user_ids)
    invalid = blocked | non_customers
    if invalid:
        raise InvalidTargetUsersError(sorted(invalid))


def _apply_service_area_filter(queryset: QuerySet[CustomerProfile], public_id: str) -> QuerySet[CustomerProfile]:
    from service_area.models import ServiceArea, ServiceAreaRequest

    try:
        area = ServiceArea.objects.get(public_id=public_id)
    except ServiceArea.DoesNotExist as exc:
        raise ValidationError(
            {'target': {'filters': {'service_area_public_id': ['Service area not found.']}}}
        ) from exc

    customer_ids = (
        ServiceAreaRequest.objects.filter(
            matched_service_area=area,
            customer_profile__isnull=False,
            is_serviceable=True,
        )
        .values_list('customer_profile_id', flat=True)
        .distinct()
    )
    return queryset.filter(pk__in=customer_ids)


def _filters_to_querydict(filters: dict) -> QueryDict:
    qd = QueryDict(mutable=True)
    for key, value in filters.items():
        if value is not None:
            qd[key] = str(value)
    return qd


def resolve_target_users(target: dict) -> QuerySet[User]:
    target_type = (target or {}).get('type', '').strip()

    if target_type == 'user':
        user_id = target.get('user_id')
        if user_id is None:
            raise ValidationError({'target': ['user_id is required for single-user targeting.']})
        _reject_non_customer_users([user_id])
        return _customer_user_queryset().filter(pk=user_id)

    if target_type == 'users':
        user_ids = target.get('user_ids') or []
        if not user_ids:
            raise ValidationError({'target': ['user_ids must not be empty.']})
        _reject_non_customer_users(user_ids)
        return _customer_user_queryset().filter(pk__in=user_ids)

    if target_type == 'filter':
        filters = target.get('filters') or {}
        unknown = sorted(set(filters.keys()) - PUSH_FILTER_ALLOWLIST)
        if unknown:
            raise ValidationError(
                {'target': {'filters': [f'Unsupported filter key(s): {", ".join(unknown)}.']}}
            )

        queryset = customer_base_queryset()
        service_area_id = filters.pop('service_area_public_id', None)
        if service_area_id:
            queryset = _apply_service_area_filter(queryset, str(service_area_id))

        remaining = _filters_to_querydict(filters)
        queryset = apply_customer_list_filters(queryset, remaining)
        return User.objects.filter(pk__in=queryset.values_list('user_id', flat=True))

    if target_type == 'all':
        return _customer_user_queryset()

    raise ValidationError({'target': ['Invalid target type. Must be user, users, filter, or all.']})


def count_eligible_users(target: dict) -> int:
    return resolve_target_users(target).count()


def is_push_enabled_for_user(user_id: int) -> bool:
    try:
        pref = NotificationPreference.objects.get(user_id=user_id)
    except NotificationPreference.DoesNotExist:
        return True
    return pref.push_enabled


def resolve_delivery_targets(user_ids: list[int]) -> list[dict]:
    """
    Build delivery rows for campaign creation.

    Each item: user_id, device_id (nullable), token (nullable), status, error_message.
    """
    if not user_ids:
        return []

    push_prefs = {
        row['user_id']: row['push_enabled']
        for row in NotificationPreference.objects.filter(user_id__in=user_ids).values(
            'user_id', 'push_enabled'
        )
    }
    devices = list(
        DeviceToken.objects.filter(user_id__in=user_ids, is_active=True)
        .exclude(token='')
        .values('id', 'user_id', 'token')
    )
    devices_by_user: dict[int, list[dict]] = {}
    for device in devices:
        devices_by_user.setdefault(device['user_id'], []).append(device)

    rows: list[dict] = []
    for user_id in user_ids:
        push_enabled = push_prefs.get(user_id, True)
        if not push_enabled:
            rows.append(
                {
                    'user_id': user_id,
                    'device_id': None,
                    'token': None,
                    'status': 'skipped',
                    'error_message': 'Push notifications disabled by user',
                }
            )
            continue

        user_devices = devices_by_user.get(user_id, [])
        if not user_devices:
            rows.append(
                {
                    'user_id': user_id,
                    'device_id': None,
                    'token': None,
                    'status': 'failed',
                    'error_message': 'No active device',
                }
            )
            continue

        for device in user_devices:
            rows.append(
                {
                    'user_id': user_id,
                    'device_id': device['id'],
                    'token': device['token'],
                    'status': 'pending',
                    'error_message': '',
                }
            )

    return rows
