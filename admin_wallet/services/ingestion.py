"""Automatic Admin Wallet movements from customer wallet funding events."""

from __future__ import annotations

from django.conf import settings

from admin_wallet.models import AdminWalletTransaction
from admin_wallet.services.ledger import credit_admin_wallet, debit_admin_wallet
from orders.models import OrderDelivery
from wallet.models import WalletTransaction

MEAL_PAYMENT_IDEMPOTENCY_PREFIX = 'meal-payment:'
CUSTOMER_RECHARGE_IDEMPOTENCY_PREFIX = 'customer-recharge:'
CUSTOMER_WITHDRAW_IDEMPOTENCY_PREFIX = 'customer-withdraw:'


def meal_payment_credit_enabled() -> bool:
    """Deprecated cash path; default off under custody accounting."""
    return bool(getattr(settings, 'ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED', False))


def customer_funding_credit_enabled() -> bool:
    return bool(getattr(settings, 'ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED', True))


def meal_payment_idempotency_key(delivery: OrderDelivery) -> str:
    return f'{MEAL_PAYMENT_IDEMPOTENCY_PREFIX}{delivery.public_id}'


def customer_recharge_idempotency_key(customer_txn: WalletTransaction) -> str:
    return f'{CUSTOMER_RECHARGE_IDEMPOTENCY_PREFIX}{customer_txn.public_id}'


def customer_withdraw_idempotency_key(customer_txn: WalletTransaction) -> str:
    return f'{CUSTOMER_WITHDRAW_IDEMPOTENCY_PREFIX}{customer_txn.public_id}'


def credit_from_customer_recharge(
    customer_txn: WalletTransaction,
) -> AdminWalletTransaction | None:
    """
    Credit Admin Wallet for a completed customer wallet recharge (custody in).

    Idempotent per customer txn via ``customer-recharge:{txn.public_id}``.
    """
    if not customer_funding_credit_enabled():
        return None

    customer = customer_txn.wallet.customer
    amount = customer_txn.amount
    key = customer_recharge_idempotency_key(customer_txn)
    note = f'Customer Wallet Funding | Txn {customer_txn.public_id}'
    metadata = {
        'purpose': 'customer_wallet_recharge',
        'customer_wallet_transaction_public_id': str(customer_txn.public_id),
        'customer_public_id': str(getattr(customer, 'public_id', '') or ''),
    }
    return credit_admin_wallet(
        amount,
        type=AdminWalletTransaction.Type.CUSTOMER_FUNDING,
        method=AdminWalletTransaction.Method.MANUAL,
        status=AdminWalletTransaction.Status.COMPLETED,
        note=note,
        reason='Customer wallet recharge',
        source='Customer Wallet Funding',
        reference=f'Recharge {customer_txn.public_id}',
        idempotency_key=key,
        metadata=metadata,
        customer=customer,
        customer_wallet_transaction=customer_txn,
    )


def debit_from_customer_withdraw(
    customer_txn: WalletTransaction,
) -> AdminWalletTransaction | None:
    """
    Debit Admin Wallet for a completed customer wallet withdraw (custody out).

    Idempotent per customer txn via ``customer-withdraw:{txn.public_id}``.
    Raises ``InsufficientFundsError`` when platform float is too low.
    """
    if not customer_funding_credit_enabled():
        return None

    customer = customer_txn.wallet.customer
    amount = customer_txn.amount
    key = customer_withdraw_idempotency_key(customer_txn)
    note = f'Customer Wallet Withdraw | Txn {customer_txn.public_id}'
    metadata = {
        'purpose': 'customer_wallet_withdraw',
        'customer_wallet_transaction_public_id': str(customer_txn.public_id),
        'customer_public_id': str(getattr(customer, 'public_id', '') or ''),
    }
    return debit_admin_wallet(
        amount,
        type=AdminWalletTransaction.Type.CUSTOMER_WITHDRAW,
        method=AdminWalletTransaction.Method.MANUAL,
        status=AdminWalletTransaction.Status.COMPLETED,
        note=note,
        reason='Customer wallet withdraw',
        source='Customer Wallet Withdraw',
        reference=f'Withdraw {customer_txn.public_id}',
        idempotency_key=key,
        metadata=metadata,
        customer=customer,
        customer_wallet_transaction=customer_txn,
    )


def credit_from_meal_payment(
    delivery: OrderDelivery,
    customer_txn: WalletTransaction,
) -> AdminWalletTransaction | None:
    """
    Legacy emergency path: cash-credit Admin Wallet for a meal charge.

    Disabled by default (``ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED=False``).
    Custody accounting credits on recharge instead; enabling this risks double-count.
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
