"""Wallet balance threshold automation: meal-stop, reminders, admin summary."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from orders.models import CustomerSubscription, OrderWalletSettings
from orders.services.meal_off import get_meal_off_settings, meal_off_business_now
from orders.services.order_wallet_settings import get_order_wallet_settings
from user_management.models import CustomerAddress, CustomerProfile
from user_management.validators import format_bd_phone_readable
from wallet.models import Wallet
from wallet.services.ledger import get_or_create_wallet

logger = logging.getLogger(__name__)


@dataclass
class AffectedUserRow:
    customer_id: int
    name: str
    phone: str
    package_name: str
    balance: Decimal
    address: str
    status: str  # Low Balance | Meal Stopped


@dataclass
class WalletThresholdRunResult:
    business_date: date
    dry_run: bool = False
    evaluated: int = 0
    reminded: int = 0
    stopped: int = 0
    resumed: int = 0
    errors: int = 0
    affected: list[AffectedUserRow] = field(default_factory=list)

    def as_log_dict(self) -> dict:
        return {
            'business_date': self.business_date.isoformat(),
            'dry_run': self.dry_run,
            'evaluated': self.evaluated,
            'reminded': self.reminded,
            'stopped': self.stopped,
            'resumed': self.resumed,
            'errors': self.errors,
            'affected_count': len(self.affected),
        }


def business_today() -> date:
    return meal_off_business_now(get_meal_off_settings()).date()


def apply_meal_service_block(customer: CustomerProfile, *, at=None) -> bool:
    """
    Mark customer meal service blocked for low balance.
    Returns True if this call newly blocked the customer.
    """
    if customer.meal_service_blocked_low_balance:
        return False
    customer.meal_service_blocked_low_balance = True
    customer.meal_service_blocked_at = at or timezone.now()
    customer.save(
        update_fields=['meal_service_blocked_low_balance', 'meal_service_blocked_at', 'updated_at']
    )
    return True


def clear_meal_service_block(customer: CustomerProfile) -> bool:
    """Clear low-balance meal-service block. Returns True if a block was cleared."""
    if not customer.meal_service_blocked_low_balance:
        return False
    customer.meal_service_blocked_low_balance = False
    customer.meal_service_blocked_at = None
    customer.save(
        update_fields=['meal_service_blocked_low_balance', 'meal_service_blocked_at', 'updated_at']
    )
    return True


def mark_low_balance_reminder_sent(customer: CustomerProfile, business_date: date) -> None:
    customer.last_low_balance_reminder_on = business_date
    customer.save(update_fields=['last_low_balance_reminder_on', 'updated_at'])


def customer_display_name(customer: CustomerProfile) -> str:
    user = customer.user
    return (user.get_full_name() or user.username or user.email or 'Customer').strip()


def customer_phone(customer: CustomerProfile) -> str:
    formatted = format_bd_phone_readable(customer.phone)
    return formatted or 'N/A'


def customer_address_text(customer: CustomerProfile) -> str:
    place = None
    pref = getattr(customer, 'meal_delivery_preference', None)
    if pref is not None:
        place = pref.lunch_place or pref.dinner_place
    if place is not None:
        parts = [place.full_address]
        if place.area:
            parts.append(place.area)
        if place.city:
            parts.append(place.city)
        return ', '.join(p for p in parts if p).strip() or 'N/A'

    present = (
        customer.addresses.filter(address_type=CustomerAddress.AddressType.PRESENT)
        .order_by('-is_default_delivery', '-id')
        .first()
    )
    if present is None:
        return 'N/A'
    parts = [present.full_address]
    if present.area:
        parts.append(present.area)
    if present.city:
        parts.append(present.city)
    return ', '.join(p for p in parts if p).strip() or 'N/A'


def active_package_name(customer: CustomerProfile) -> str:
    sub = (
        CustomerSubscription.objects.filter(
            customer=customer,
            status=CustomerSubscription.Status.ACTIVE,
        )
        .order_by('-created_at')
        .first()
    )
    if sub is None:
        return 'N/A'
    return (sub.meal_name_snapshot or 'N/A').strip() or 'N/A'


def spendable_balance(customer: CustomerProfile) -> Decimal:
    try:
        wallet = customer.wallet
    except Wallet.DoesNotExist:
        wallet = get_or_create_wallet(customer)
    return Decimal(wallet.balance).quantize(Decimal('0.01'))


def maybe_resume_after_wallet_credit(customer: CustomerProfile | None) -> bool:
    """
    Best-effort auto-resume when spendable balance recovers to meal-stop threshold.
    Safe to call from credit_wallet on_commit; never raises.
    """
    if customer is None:
        return False
    try:
        customer.refresh_from_db(
            fields=['meal_service_blocked_low_balance', 'meal_service_blocked_at']
        )
        if not customer.meal_service_blocked_low_balance:
            return False
        settings_obj = get_order_wallet_settings()
        balance = spendable_balance(customer)
        if balance >= settings_obj.meal_stop_threshold:
            return clear_meal_service_block(customer)
    except Exception:
        logger.exception(
            'Failed meal-stop resume after credit customer_id=%s',
            getattr(customer, 'pk', None),
        )
    return False


def candidate_customers_queryset():
    """Active subscribers and currently blocked customers (for resume)."""
    active_ids = CustomerSubscription.objects.filter(
        status=CustomerSubscription.Status.ACTIVE,
    ).values_list('customer_id', flat=True)
    return (
        CustomerProfile.objects.filter(
            Q(pk__in=active_ids) | Q(meal_service_blocked_low_balance=True),
            is_email_verified=True,
            user__is_active=True,
        )
        .select_related('user', 'wallet', 'meal_delivery_preference')
        .select_related(
            'meal_delivery_preference__lunch_place',
            'meal_delivery_preference__dinner_place',
        )
        .prefetch_related('addresses')
        .distinct()
        .order_by('id')
    )


def _build_row(
    customer: CustomerProfile,
    *,
    balance: Decimal,
    status_label: str,
) -> AffectedUserRow:
    return AffectedUserRow(
        customer_id=customer.pk,
        name=customer_display_name(customer),
        phone=customer_phone(customer),
        package_name=active_package_name(customer),
        balance=balance,
        address=customer_address_text(customer),
        status=status_label,
    )


def run_wallet_threshold_check(
    *,
    as_of: date | None = None,
    dry_run: bool = False,
) -> WalletThresholdRunResult:
    """
    Evaluate wallet thresholds for active/blocked customers.

    Priority per customer:
    1. balance < meal_stop → block (+ notify on transition)
    2. else if blocked and balance >= meal_stop → resume
    3. else if balance < reminder → remind (once per business day)
    """
    from notifications.services.wallet_threshold_notifications import (
        notify_admins_low_balance_summary,
        notify_customer_low_balance_reminder,
        notify_customer_meal_stop,
    )

    business_date = as_of or business_today()
    settings_obj: OrderWalletSettings = get_order_wallet_settings()
    reminder_threshold = settings_obj.low_balance_reminder_threshold
    stop_threshold = settings_obj.meal_stop_threshold

    result = WalletThresholdRunResult(business_date=business_date, dry_run=dry_run)
    affected_by_id: dict[int, AffectedUserRow] = {}

    for customer in candidate_customers_queryset().iterator(chunk_size=100):
        result.evaluated += 1
        try:
            balance = spendable_balance(customer)
            was_blocked = customer.meal_service_blocked_low_balance

            if balance < stop_threshold:
                newly_blocked = False
                if dry_run:
                    newly_blocked = not was_blocked
                    if newly_blocked:
                        result.stopped += 1
                else:
                    with transaction.atomic():
                        locked = CustomerProfile.objects.select_for_update().get(pk=customer.pk)
                        newly_blocked = apply_meal_service_block(locked)
                        customer.meal_service_blocked_low_balance = True
                        if newly_blocked:
                            result.stopped += 1
                    if newly_blocked:
                        notify_customer_meal_stop(
                            customer,
                            balance=balance,
                            meal_stop_threshold=stop_threshold,
                        )
                affected_by_id[customer.pk] = _build_row(
                    customer, balance=balance, status_label='Meal Stopped'
                )
                continue

            if was_blocked and balance >= stop_threshold:
                if dry_run:
                    result.resumed += 1
                else:
                    with transaction.atomic():
                        locked = CustomerProfile.objects.select_for_update().get(pk=customer.pk)
                        if clear_meal_service_block(locked):
                            result.resumed += 1
                            customer.meal_service_blocked_low_balance = False

            if balance < reminder_threshold:
                already_reminded = customer.last_low_balance_reminder_on == business_date
                if dry_run:
                    if not already_reminded:
                        result.reminded += 1
                elif not already_reminded:
                    notify_customer_low_balance_reminder(
                        customer,
                        balance=balance,
                        reminder_threshold=reminder_threshold,
                        meal_stop_threshold=stop_threshold,
                    )
                    mark_low_balance_reminder_sent(customer, business_date)
                    result.reminded += 1
                if customer.pk not in affected_by_id:
                    affected_by_id[customer.pk] = _build_row(
                        customer, balance=balance, status_label='Low Balance'
                    )
        except Exception:
            result.errors += 1
            logger.exception(
                'Wallet threshold check failed customer_id=%s',
                getattr(customer, 'pk', None),
            )

    result.affected = list(affected_by_id.values())
    if not dry_run:
        try:
            notify_admins_low_balance_summary(
                affected=result.affected,
                business_date=business_date,
            )
        except Exception:
            result.errors += 1
            logger.exception('Admin low-balance summary email failed')

    return result
