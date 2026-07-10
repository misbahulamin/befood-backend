from django.db import transaction

from ..models import CustomerAddress, CustomerProfile
from .profile_completion import update_profile_completion


def get_default_delivery_address(customer_profile):
    return customer_profile.addresses.filter(is_default_delivery=True).first()


def ensure_single_default_delivery(customer_profile, exclude_address_id=None):
    defaults = customer_profile.addresses.filter(is_default_delivery=True)
    if exclude_address_id is not None:
        defaults = defaults.exclude(pk=exclude_address_id)
    defaults.update(is_default_delivery=False)


def set_default_delivery_address(customer_profile, address):
    if address.customer_profile_id != customer_profile.id:
        raise ValueError('Address does not belong to this customer.')
    if address.address_type != CustomerAddress.AddressType.PRESENT:
        raise ValueError('Only present addresses can be set as default delivery.')

    with transaction.atomic():
        ensure_single_default_delivery(customer_profile, exclude_address_id=address.pk)
        if not address.is_default_delivery:
            address.is_default_delivery = True
            address.save(update_fields=['is_default_delivery', 'updated_at'])
        update_profile_completion(customer_profile)
    return address


def assign_default_if_first_present(customer_profile, address):
    if address.address_type != CustomerAddress.AddressType.PRESENT:
        return address

    present_count = customer_profile.addresses.filter(
        address_type=CustomerAddress.AddressType.PRESENT
    ).count()
    if present_count == 1:
        address.is_default_delivery = True
        address.save(update_fields=['is_default_delivery', 'updated_at'])
    return address


def handle_default_on_delete(customer_profile, was_default):
    if not was_default:
        return

    next_default = (
        customer_profile.addresses.filter(address_type=CustomerAddress.AddressType.PRESENT)
        .order_by('-created_at')
        .first()
    )
    if next_default:
        next_default.is_default_delivery = True
        next_default.save(update_fields=['is_default_delivery', 'updated_at'])

    update_profile_completion(customer_profile)
