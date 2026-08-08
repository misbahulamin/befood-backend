"""Automatic Admin Wallet credits from customer payment events."""

from __future__ import annotations

from django.conf import settings

from admin_wallet.models import AdminWalletTransaction
from admin_wallet.services.ledger import credit_admin_wallet
from orders.models import OrderDelivery
from wallet.models import WalletTransaction

MEAL_PAYMENT_IDEMPOTENCY_PREFIX = 'meal-payment:'


def meal_payment_credit_enabled() -> bool:
    return bool(getattr(settings, 'ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED', True))


def meal_payment_idempotency_key(delivery: OrderDelivery) -> str:
    return f'{MEAL_PAYMENT_IDEMPOTENCY_PREFIX}{delivery.public_id}'


def credit_from_meal_payment(
    delivery: OrderDelivery,
    customer_txn: WalletTransaction,
) -> AdminWalletTransaction | None:
    """
    Credit Admin Wallet for a completed customer meal-delivery wallet charge.

    Idempotent per delivery via ``meal-payment:{delivery.public_id}``.
    Intended to run in the same atomic block as ``charge_delivered_meal``.
    """
    if not meal_payment_credit_enabled():
        return None

    order = delivery.order
    amount = customer_txn.amount
    key = meal_payment_idempotency_key(delivery)
    note = (
        f'Customer Order Payment | Order {order.public_id} | '
        f'Delivery {delivery.public_id}'
    )
    metadata = {
        'purpose': 'meal_delivery_customer_payment',
        'order_public_id': str(order.public_id),
        'delivery_public_id': str(delivery.public_id),
        'customer_wallet_transaction_public_id': str(customer_txn.public_id),
        'service_date': delivery.service_date.isoformat(),
        'meal_period': delivery.meal_period,
    }
    return credit_admin_wallet(
        amount,
        type=AdminWalletTransaction.Type.CUSTOMER_PAYMENT,
        method=AdminWalletTransaction.Method.WALLET,
        status=AdminWalletTransaction.Status.COMPLETED,
        note=note,
        reason='Customer meal payment',
        source='Customer Order Payment',
        reference=f'Order {order.public_id}',
        idempotency_key=key,
        metadata=metadata,
        order=order,
        order_delivery=delivery,
        customer=order.customer,
        customer_wallet_transaction=customer_txn,
    )
