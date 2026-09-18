from datetime import date, datetime

from django.db.models import Q, QuerySet

from delivery_zones.models import DeliveryLocation, DeliveryZone
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.zones import zone_for_rider
from orders.models import OrderDelivery
from orders.services.meal_demand import (
    _slot_ingredient_names_for_meal,
    low_balance_blocked_q,
)
from orders.services.meal_off import get_current_delivery_period, get_meal_off_settings
from orders.services.subscription_parent import (
    delivery_customer,
    delivery_meal,
    live_delivery_q,
)
from orders.services.wallet_balance_thresholds import customer_display_name
from user_management.models import RiderProfile


def _zone_customer_q(zone: DeliveryZone) -> Q:
    return Q(subscription__customer__delivery_location__zone=zone) | Q(
        order__customer__delivery_location__zone=zone
    )


def _active_location_q() -> Q:
    return Q(
        subscription__customer__delivery_location__status=DeliveryLocation.Status.ACTIVE
    ) | Q(order__customer__delivery_location__status=DeliveryLocation.Status.ACTIVE)


def zone_scoped_deliveries(
    *,
    zone: DeliveryZone,
    service_date: date,
    meal_period: str | None = None,
    statuses: list[str] | None = None,
    include_low_balance_blocked: bool = False,
) -> QuerySet[OrderDelivery]:
    """
    Zone-scoped live deliveries for a service date.

    By default omits customers with meal_service_blocked_low_balance (same rule
    as kitchen cooking eligibility / auto-delivery), so rider boards do not list
    meal-on customers who will not be cooked for.
    """
    qs = (
        OrderDelivery.objects.select_related(
            'order',
            'order__customer__user',
            'order__customer__delivery_location',
            'order__customer__delivery_location__zone',
            'order__meal',
            'subscription',
            'subscription__customer__user',
            'subscription__customer__delivery_location',
            'subscription__customer__delivery_location__zone',
            'subscription__meal',
        )
        .filter(live_delivery_q(service_date), service_date=service_date)
        .filter(_zone_customer_q(zone))
        .filter(_active_location_q())
    )
    if meal_period:
        qs = qs.filter(meal_period=meal_period)
    if statuses:
        qs = qs.filter(status__in=statuses)
    if not include_low_balance_blocked:
        qs = qs.exclude(low_balance_blocked_q())
    return qs


def _delivery_location(delivery: OrderDelivery) -> DeliveryLocation | None:
    customer = delivery_customer(delivery)
    if customer is None:
        return None
    return customer.delivery_location


def _meal_quantity(delivery: OrderDelivery) -> int:
    """Subscription slots are 1 meal; historical order items may carry quantity."""
    if delivery.order_id:
        first_item = delivery.order.items.order_by('id').first()
        if first_item is not None and first_item.quantity:
            return int(first_item.quantity)
    return 1


def _special_notes(delivery: OrderDelivery) -> str:
    if delivery.note:
        return delivery.note
    if delivery.subscription_id and delivery.subscription.customer_note:
        return delivery.subscription.customer_note
    if delivery.order_id and delivery.order.customer_note:
        return delivery.order.customer_note
    return ''


def _menu_items_label(
    delivery: OrderDelivery,
    *,
    service_date: date,
    meal_period: str,
    menu_cache: dict[int, list[str]],
) -> str:
    meal = delivery_meal(delivery)
    meal_id = meal.pk if meal is not None else None
    names = _slot_ingredient_names_for_meal(
        meal_id,
        service_date,
        meal_period,
        menu_cache,
    )
    return ' + '.join(names) if names else ''


def _empty_board(
    *,
    service_date: date,
    timezone_name: str,
    active_meal_period: str | None,
    zone: dict | None = None,
    message: str | None = None,
) -> dict:
    payload = {
        'service_date': service_date.isoformat(),
        'active_meal_period': active_meal_period,
        'timezone': timezone_name,
        'total_count': 0,
        'zone': zone,
        'periods': {},
    }
    if message:
        payload['message'] = message
    return payload


def build_deliveryman_board(
    rider: RiderProfile,
    *,
    include_delivered: bool = False,
    now: datetime | None = None,
) -> dict:
    """
    Zone-scoped today board for the active meal window only.

    Client service_date / meal_period are intentionally not accepted — the board
    always uses get_current_delivery_period() (BREAKING vs dual-period default).

    Deliveryman payloads never include customer wallet_balance.
    """
    settings_obj = get_meal_off_settings()
    service_date, active_meal_period = get_current_delivery_period(
        now,
        settings_obj=settings_obj,
    )
    timezone_name = settings_obj.timezone

    zone = zone_for_rider(rider)
    if zone is None:
        return _empty_board(
            service_date=service_date,
            timezone_name=timezone_name,
            active_meal_period=active_meal_period,
            zone=None,
            message='No delivery zone assigned.',
        )

    zone_payload = {
        'public_id': str(zone.public_id),
        'name': zone.name,
        'code': zone.code,
        'priority': zone.priority,
    }

    if active_meal_period is None:
        return _empty_board(
            service_date=service_date,
            timezone_name=timezone_name,
            active_meal_period=None,
            zone=zone_payload,
            message='No active meal delivery window yet.',
        )

    if active_meal_period not in OrderDelivery.MealPeriod.values:
        raise DeliveryZoneError(
            'meal_period must be lunch or dinner.',
            code='INVALID_MEAL_PERIOD',
        )

    statuses = [OrderDelivery.DeliveryStatus.SCHEDULED]
    if include_delivered:
        statuses.append(OrderDelivery.DeliveryStatus.DELIVERED)

    deliveries = list(
        zone_scoped_deliveries(
            zone=zone,
            service_date=service_date,
            meal_period=active_meal_period,
            statuses=statuses,
            include_low_balance_blocked=False,
        )
    )

    def sort_key(d: OrderDelivery):
        loc = _delivery_location(d)
        customer = delivery_customer(d)
        name = customer_display_name(customer) if customer else ''
        return (
            loc.priority if loc else 9999,
            loc.name if loc else '',
            name.lower(),
            str(d.public_id),
        )

    deliveries.sort(key=sort_key)

    groups: dict[str, dict] = {}
    ordered_groups = []
    menu_cache: dict[int, list[str]] = {}
    listed_count = 0
    for delivery in deliveries:
        loc = _delivery_location(delivery)
        if loc is None:
            continue
        key = str(loc.public_id)
        if key not in groups:
            group = {
                'location_public_id': key,
                'location_name': loc.name,
                'location_priority': loc.priority,
                'delivery_count': 0,
                'customers': [],
            }
            groups[key] = group
            ordered_groups.append(group)
        customer = delivery_customer(delivery)
        groups[key]['delivery_count'] += 1
        listed_count += 1
        meal_name = ''
        if delivery.subscription_id:
            meal_name = delivery.subscription.meal_name_snapshot or ''
        elif delivery.order_id:
            meal_name = delivery.order.meal_name_snapshot or ''
        groups[key]['customers'].append(
            {
                'delivery_public_id': str(delivery.public_id),
                'customer_public_id': str(customer.public_id) if customer else None,
                'customer_name': customer_display_name(customer) if customer else None,
                'customer_email': customer.user.email if customer else None,
                'customer_phone': customer.phone if customer else None,
                'status': delivery.status,
                'address_label': delivery.delivery_label_snapshot,
                'full_address': delivery.delivery_full_address_snapshot,
                'area': delivery.delivery_area_snapshot,
                'city': delivery.delivery_city_snapshot,
                'location_name': loc.name,
                'location_priority': loc.priority,
                'meal_period': delivery.meal_period,
                'meal_name': meal_name,
                'meal_quantity': _meal_quantity(delivery),
                'notes': _special_notes(delivery),
                'menu_items_label': _menu_items_label(
                    delivery,
                    service_date=service_date,
                    meal_period=active_meal_period,
                    menu_cache=menu_cache,
                ),
            }
        )

    return {
        'service_date': service_date.isoformat(),
        'active_meal_period': active_meal_period,
        'timezone': timezone_name,
        'total_count': listed_count,
        'zone': zone_payload,
        'periods': {
            active_meal_period: {
                'total_count': listed_count,
                'locations': ordered_groups,
            }
        },
    }


def delivery_in_rider_zone(delivery: OrderDelivery, rider: RiderProfile) -> bool:
    zone = zone_for_rider(rider)
    if zone is None:
        return False
    loc = _delivery_location(delivery)
    if loc is None or loc.zone_id is None:
        return False
    return loc.zone_id == zone.pk
