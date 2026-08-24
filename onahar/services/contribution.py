from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from onahar.models import (
    OnaharContribution,
    OnaharFundLedgerEntry,
    OnaharMonthlyProgress,
    OnaharPointEvent,
    OnaharTargetHistory,
)
from onahar.services.audit import write_audit
from onahar.services.fund import credit_fund, debit_fund, get_or_create_settings, lock_settings
from onahar.services.privacy import current_year_month


class OnaharError(Exception):
    def __init__(self, message: str, code: str = 'ONAHAR_ERROR'):
        super().__init__(message)
        self.code = code


def is_onahar_enabled() -> bool:
    return getattr(settings, 'ONAHAR_ENABLED', True)


def _open_or_get_progress(customer, year_month: str) -> OnaharMonthlyProgress:
    progress = (
        OnaharMonthlyProgress.objects.select_for_update()
        .filter(customer=customer, year_month=year_month)
        .first()
    )
    if progress is not None:
        return progress
    target = get_or_create_settings().contribution_target
    try:
        return OnaharMonthlyProgress.objects.create(
            customer=customer,
            year_month=year_month,
            target_snapshot=target,
            status=OnaharMonthlyProgress.Status.OPEN,
        )
    except IntegrityError:
        return (
            OnaharMonthlyProgress.objects.select_for_update()
            .get(customer=customer, year_month=year_month)
        )


def _issue_missing_contributions(progress: OnaharMonthlyProgress, actor=None) -> list[OnaharContribution]:
    """Create earned contributions up to floor(net/target) and credit fund."""
    if progress.status != OnaharMonthlyProgress.Status.OPEN:
        return []
    target = progress.target_snapshot
    if target < 1:
        return []
    expected = max(0, progress.net_points // target)
    missing = expected - progress.contributions_earned
    created = []
    for _ in range(missing):
        contribution = OnaharContribution.objects.create(
            customer=progress.customer,
            year_month=progress.year_month,
            meals=1,
            kind=OnaharContribution.Kind.EARNED,
            monthly_progress=progress,
        )
        credit_fund(
            meals=1,
            entry_type=OnaharFundLedgerEntry.EntryType.CONTRIBUTION,
            contribution=contribution,
            note=f'Contribution from {progress.year_month}',
            actor=actor,
            audit_action='contribution_generated',
        )
        created.append(contribution)
        write_audit(
            action='contribution_generated',
            actor=actor,
            new_value={
                'contribution_public_id': str(contribution.public_id),
                'customer_public_id': str(progress.customer.public_id),
                'year_month': progress.year_month,
                'meals': 1,
            },
        )
    if missing > 0:
        progress.contributions_earned = expected
        progress.save(update_fields=['contributions_earned', 'updated_at'])
    return created


def _adjust_excess_contributions(progress: OnaharMonthlyProgress, actor=None) -> list[OnaharContribution]:
    """When net points drop, compensate excess earned contributions."""
    target = progress.target_snapshot
    allowed = max(0, progress.net_points // target) if target >= 1 else 0
    excess = progress.contributions_earned - allowed
    created = []
    for _ in range(max(0, excess)):
        adjustment = OnaharContribution.objects.create(
            customer=progress.customer,
            year_month=progress.year_month,
            meals=-1,
            kind=OnaharContribution.Kind.ADJUSTMENT,
            monthly_progress=progress,
            note='Refund/reversal adjustment',
        )
        debit_fund(
            meals=1,
            entry_type=OnaharFundLedgerEntry.EntryType.CONTRIBUTION_ADJUSTMENT,
            contribution=adjustment,
            note='Contribution adjustment after reversal',
            actor=actor,
            audit_action='contribution_adjusted',
            enforce_available=False,
        )
        # Bypass available check for adjustments: re-read lock path already may go negative.
        created.append(adjustment)
        write_audit(
            action='contribution_adjusted',
            actor=actor,
            new_value={
                'contribution_public_id': str(adjustment.public_id),
                'meals': -1,
                'year_month': progress.year_month,
            },
        )
    if excess > 0:
        progress.contributions_earned = allowed
        progress.save(update_fields=['contributions_earned', 'updated_at'])
    return created


@transaction.atomic
def credit_for_delivery(delivery, actor=None) -> OnaharPointEvent | None:
    if not is_onahar_enabled():
        return None

    from orders.models import OrderDelivery

    locked = (
        OrderDelivery.objects.select_for_update()
        .select_related(
            'order__customer__user',
            'subscription__customer__user',
        )
        .get(pk=delivery.pk)
    )
    if locked.status != OrderDelivery.DeliveryStatus.DELIVERED:
        return None

    from orders.services.subscription_parent import delivery_customer

    customer = delivery_customer(locked)
    if customer is None:
        return None
    # Attribute points to the meal service date's calendar month (project TZ dates).
    year_month = locked.service_date.strftime('%Y-%m')

    if OnaharPointEvent.objects.filter(
        order_delivery=locked,
        event_type=OnaharPointEvent.EventType.CREDIT,
    ).exists():
        return OnaharPointEvent.objects.get(
            order_delivery=locked,
            event_type=OnaharPointEvent.EventType.CREDIT,
        )

    progress = _open_or_get_progress(customer, year_month)
    if progress.status == OnaharMonthlyProgress.Status.CLOSED:
        # Late credit into a closed month: reopen is not allowed; attribute to current open month.
        year_month = current_year_month()
        progress = _open_or_get_progress(customer, year_month)

    try:
        event = OnaharPointEvent.objects.create(
            customer=customer,
            order_delivery=locked,
            event_type=OnaharPointEvent.EventType.CREDIT,
            year_month=year_month,
            points_delta=1,
        )
    except IntegrityError:
        return OnaharPointEvent.objects.get(
            order_delivery=locked,
            event_type=OnaharPointEvent.EventType.CREDIT,
        )

    progress.net_points += 1
    progress.save(update_fields=['net_points', 'updated_at'])
    _issue_missing_contributions(progress, actor=actor)
    return event


@transaction.atomic
def reverse_for_delivery(delivery, actor=None) -> OnaharPointEvent | None:
    if not is_onahar_enabled():
        return None

    from orders.models import OrderDelivery

    locked = OrderDelivery.objects.select_for_update().select_related('order__customer').get(
        pk=delivery.pk
    )
    credit = OnaharPointEvent.objects.filter(
        order_delivery=locked,
        event_type=OnaharPointEvent.EventType.CREDIT,
    ).first()
    if credit is None:
        return None
    if OnaharPointEvent.objects.filter(
        order_delivery=locked,
        event_type=OnaharPointEvent.EventType.REVERSE,
    ).exists():
        return OnaharPointEvent.objects.get(
            order_delivery=locked,
            event_type=OnaharPointEvent.EventType.REVERSE,
        )

    year_month = credit.year_month
    progress = _open_or_get_progress(locked.order.customer, year_month)

    try:
        event = OnaharPointEvent.objects.create(
            customer=locked.order.customer,
            order_delivery=locked,
            event_type=OnaharPointEvent.EventType.REVERSE,
            year_month=year_month,
            points_delta=-1,
        )
    except IntegrityError:
        return OnaharPointEvent.objects.get(
            order_delivery=locked,
            event_type=OnaharPointEvent.EventType.REVERSE,
        )

    progress.net_points = max(0, progress.net_points - 1)
    progress.save(update_fields=['net_points', 'updated_at'])
    _adjust_excess_contributions(progress, actor=actor)
    write_audit(
        action='point_reversed',
        actor=actor,
        new_value={
            'delivery_public_id': str(locked.public_id),
            'year_month': year_month,
            'net_points': progress.net_points,
        },
    )
    return event


@transaction.atomic
def close_month(year_month: str, actor=None) -> dict:
    """Idempotently close all open progress rows for year_month."""
    closed = 0
    skipped = 0
    qs = OnaharMonthlyProgress.objects.select_for_update().filter(year_month=year_month)
    for progress in qs:
        if progress.status == OnaharMonthlyProgress.Status.CLOSED:
            skipped += 1
            continue
        _issue_missing_contributions(progress, actor=actor)
        remainder = progress.net_points % progress.target_snapshot if progress.target_snapshot else 0
        progress.expired_points = remainder
        progress.status = OnaharMonthlyProgress.Status.CLOSED
        progress.closed_at = timezone.now()
        progress.save(
            update_fields=['expired_points', 'status', 'closed_at', 'updated_at']
        )
        write_audit(
            action='monthly_points_expired',
            actor=actor,
            new_value={
                'year_month': year_month,
                'customer_public_id': str(progress.customer.public_id),
                'expired_points': remainder,
                'contributions_earned': progress.contributions_earned,
            },
        )
        closed += 1

    write_audit(
        action='month_closed',
        actor=actor,
        new_value={'year_month': year_month, 'closed': closed, 'skipped': skipped},
    )
    return {'year_month': year_month, 'closed': closed, 'skipped': skipped}


@transaction.atomic
def update_contribution_target(new_target: int, actor=None) -> dict:
    if not isinstance(new_target, int) or new_target < 1:
        raise OnaharError('contribution_target must be an integer >= 1.', code='INVALID_TARGET')

    settings_obj = lock_settings()
    previous = settings_obj.contribution_target
    if previous == new_target:
        return {'previous_target': previous, 'new_target': new_target, 'changed': False}

    settings_obj.contribution_target = new_target
    settings_obj.save(update_fields=['contribution_target', 'updated_at'])
    OnaharTargetHistory.objects.create(
        previous_target=previous,
        new_target=new_target,
        changed_by=actor,
    )
    write_audit(
        action='target_changed',
        actor=actor,
        previous_value={'contribution_target': previous},
        new_value={'contribution_target': new_target},
    )
    return {'previous_target': previous, 'new_target': new_target, 'changed': True}
