from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from orders.models import OrderDelivery
from user_management.models import CustomerDeliveryPlace, CustomerProfile
from user_management.services.delivery_preference import resolve_delivery_address, today_in_meal_tz


def snapshot_fields_from_place(place: CustomerDeliveryPlace | None) -> dict:
    if place is None:
        return {
            'delivery_place': None,
            'delivery_label_snapshot': '',
            'delivery_full_address_snapshot': '',
            'delivery_area_snapshot': '',
            'delivery_city_snapshot': '',
            'delivery_latitude_snapshot': None,
            'delivery_longitude_snapshot': None,
        }
    return {
        'delivery_place': place,
        'delivery_label_snapshot': place.label,
        'delivery_full_address_snapshot': place.full_address,
        'delivery_area_snapshot': place.area or '',
        'delivery_city_snapshot': place.city or '',
        'delivery_latitude_snapshot': place.latitude,
        'delivery_longitude_snapshot': place.longitude,
    }


def apply_delivery_snapshot(delivery: OrderDelivery, place: CustomerDeliveryPlace | None) -> OrderDelivery:
    fields = snapshot_fields_from_place(place)
    for key, value in fields.items():
        setattr(delivery, key, value)
    return delivery


def resolve_and_apply_snapshot(
    delivery: OrderDelivery,
    customer_profile: CustomerProfile | None = None,
) -> OrderDelivery:
    profile = customer_profile
    if profile is None and delivery.subscription_id:
        profile = delivery.subscription.customer
    if profile is None and delivery.order_id:
        profile = delivery.order.customer
    place = resolve_delivery_address(profile, delivery.service_date, delivery.meal_period)
    apply_delivery_snapshot(delivery, place)
    return delivery


@transaction.atomic
def resync_future_scheduled_deliveries(
    customer_profile: CustomerProfile,
    *,
    reference_date: date | None = None,
) -> int:
    """
    Re-resolve address snapshots for future scheduled deliveries only.
    Returns number of rows updated.
    """
    today = reference_date or today_in_meal_tz()
    qs = (
        OrderDelivery.objects.select_related('order', 'subscription')
        .filter(
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
            service_date__gte=today,
        )
        .filter(
            Q(order__customer=customer_profile)
            | Q(subscription__customer=customer_profile)
        )
        .select_for_update()
    )
    updated = 0
    for delivery in qs:
        resolve_and_apply_snapshot(delivery, customer_profile)
        delivery.save(
            update_fields=[
                'delivery_place',
                'delivery_label_snapshot',
                'delivery_full_address_snapshot',
                'delivery_area_snapshot',
                'delivery_city_snapshot',
                'delivery_latitude_snapshot',
                'delivery_longitude_snapshot',
                'updated_at',
            ]
        )
        updated += 1
    return updated


def backfill_missing_scheduled_snapshots(*, reference_date: date | None = None) -> int:
    """Fill snapshots for scheduled future deliveries that have empty address snapshot."""
    today = reference_date or today_in_meal_tz()
    qs = OrderDelivery.objects.select_related('order', 'order__customer').filter(
        status=OrderDelivery.DeliveryStatus.SCHEDULED,
        service_date__gte=today,
        delivery_full_address_snapshot='',
    )
    updated = 0
    for delivery in qs.iterator():
        resolve_and_apply_snapshot(delivery)
        delivery.save(
            update_fields=[
                'delivery_place',
                'delivery_label_snapshot',
                'delivery_full_address_snapshot',
                'delivery_area_snapshot',
                'delivery_city_snapshot',
                'delivery_latitude_snapshot',
                'delivery_longitude_snapshot',
                'updated_at',
            ]
        )
        updated += 1
    return updated
