"""Best-effort push when a meal delivery is marked delivered."""

from __future__ import annotations

import logging

from notifications.services.device_service import get_user_device_tokens
from notifications.services.fcm_service import FCMNotConfiguredError, send_to_tokens
from orders.services.subscription_parent import delivery_customer, delivery_meal_name

logger = logging.getLogger(__name__)


def notify_meal_delivered(delivery) -> None:
    """
    Send FCM to the delivery customer after a successful mark-delivered.

    Never raises into callers — delivery status and wallet charge must stay committed.
    """
    try:
        customer = delivery_customer(delivery)
        if customer is None or getattr(customer, 'user_id', None) is None:
            logger.info(
                'Skipping meal-delivered notify: no customer for delivery_id=%s',
                getattr(delivery, 'pk', None),
            )
            return

        tokens = get_user_device_tokens(customer.user)
        if not tokens:
            logger.info(
                'Skipping meal-delivered notify: no active device tokens user_id=%s delivery_id=%s',
                customer.user_id,
                getattr(delivery, 'pk', None),
            )
            return

        meal_name = delivery_meal_name(delivery) or 'your meal'
        period = (delivery.meal_period or 'meal').capitalize()
        service_date = delivery.service_date.isoformat() if delivery.service_date else ''
        title = 'Meal delivered'
        body = f'{period} ({meal_name}) for {service_date} has been delivered.'
        data = {
            'type': 'meal_delivered',
            'delivery_public_id': str(delivery.public_id),
            'meal_period': delivery.meal_period or '',
            'service_date': service_date,
        }
        if delivery.subscription_id:
            data['subscription_public_id'] = str(delivery.subscription.public_id)
        if delivery.order_id:
            data['order_public_id'] = str(delivery.order.public_id)

        send_to_tokens(tokens, title, body, data)
    except FCMNotConfiguredError:
        logger.info(
            'FCM not configured; skipped meal-delivered notify delivery_id=%s',
            getattr(delivery, 'pk', None),
        )
    except Exception:
        logger.exception(
            'Meal-delivered notification failed delivery_id=%s',
            getattr(delivery, 'pk', None),
        )
