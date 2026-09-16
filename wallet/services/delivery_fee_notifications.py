"""Best-effort customer inbox + FCM after delivery-fee deduction."""

from __future__ import annotations

import calendar
import logging

from notifications.services.device_service import get_user_device_tokens
from notifications.services.fcm_service import FCMNotConfiguredError, send_to_tokens
from notifications.services.inbox_service import create_inbox_notification
from wallet.models import DeliveryFeePayment

logger = logging.getLogger(__name__)

DELIVERY_FEE_DEDUCTED_TYPE = 'delivery_fee_deducted'
DELIVERY_FEE_SCREEN = 'wallet'


def _format_amount(value) -> str:
    return f'{value:.2f}'


def notify_customer_delivery_fee_deducted(payment_id: int) -> None:
    """
    Create inbox notification and attempt FCM push.

    Never raises into callers — wallet debit must stay committed.
    """
    try:
        payment = DeliveryFeePayment.objects.select_related(
            'customer__user',
            'wallet_transaction',
        ).get(pk=payment_id)
    except DeliveryFeePayment.DoesNotExist:
        logger.warning('Delivery-fee notify skipped: payment_id=%s missing', payment_id)
        return

    if payment.status != DeliveryFeePayment.Status.PAID:
        logger.info(
            'Delivery-fee notify skipped: status=%s payment=%s',
            payment.status,
            payment.public_id,
        )
        return

    try:
        user = payment.customer.user
    except Exception:
        logger.exception(
            'Delivery-fee notify failed loading user payment=%s',
            payment.public_id,
        )
        return

    month_name = calendar.month_name[payment.payment_month]
    amount_s = _format_amount(payment.amount)
    balance = payment.wallet_transaction.balance_after
    if balance is None:
        balance = payment.wallet_transaction.wallet.balance
    balance_s = _format_amount(balance)

    title = 'Delivery Fee Deducted'
    body = (
        f'{month_name} মাসের delivery fee হিসেবে {amount_s} টাকা '
        f'আপনার wallet থেকে deduct করা হয়েছে।\n'
        f'বর্তমান wallet balance:\n{balance_s} Tk'
    )
    data = {
        'type': DELIVERY_FEE_DEDUCTED_TYPE,
        'screen': DELIVERY_FEE_SCREEN,
        'entity_type': 'delivery_fee_payment',
        'entity_id': str(payment.public_id),
        'amount': amount_s,
        'balance': balance_s,
        'payment_month': str(payment.payment_month),
        'payment_year': str(payment.payment_year),
        'wallet_transaction_public_id': str(payment.wallet_transaction.public_id),
    }

    try:
        create_inbox_notification(
            user,
            title=title,
            body=body,
            notification_type=DELIVERY_FEE_DEDUCTED_TYPE,
            screen=DELIVERY_FEE_SCREEN,
            data=data,
        )
    except Exception:
        logger.exception(
            'Delivery-fee inbox notification failed payment=%s',
            payment.public_id,
        )

    tokens = get_user_device_tokens(user)
    if not tokens:
        logger.info(
            'Skipping delivery-fee push: no tokens user_id=%s payment=%s',
            getattr(user, 'pk', None),
            payment.public_id,
        )
        return

    try:
        send_to_tokens(tokens, title, body, data)
    except FCMNotConfiguredError:
        logger.info(
            'FCM not configured; skipped delivery-fee push payment=%s',
            payment.public_id,
        )
    except Exception:
        logger.exception('Delivery-fee push failed payment=%s', payment.public_id)
