"""Batch auto mark-delivered for scheduled lunch/dinner slots (cron)."""

from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from django.conf import settings

from orders.models import OrderDelivery
from orders.services.meal_off import get_meal_off_settings, meal_off_business_now
from orders.services.order_delivery import DeliveryError, mark_delivery_and_notify
from orders.services.subscription_parent import live_delivery_q

logger = logging.getLogger(__name__)

VALID_MEAL_PERIODS = {
    OrderDelivery.MealPeriod.LUNCH,
    OrderDelivery.MealPeriod.DINNER,
}


class AutoDeliveryLockError(Exception):
    """Raised when another auto-delivery process holds the lock."""


@dataclass
class SlotFailure:
    delivery_public_id: str
    code: str | None
    message: str


@dataclass
class AutoDeliveryRunResult:
    service_date: date
    meal_period: str
    dry_run: bool = False
    disabled: bool = False
    lock_busy: bool = False
    candidate_count: int = 0
    attempted: int = 0
    delivered: int = 0
    already_delivered: int = 0
    failed: int = 0
    failures: list[SlotFailure] = field(default_factory=list)

    def as_log_dict(self) -> dict:
        return {
            'service_date': self.service_date.isoformat(),
            'meal_period': self.meal_period,
            'dry_run': self.dry_run,
            'disabled': self.disabled,
            'lock_busy': self.lock_busy,
            'candidate_count': self.candidate_count,
            'attempted': self.attempted,
            'delivered': self.delivered,
            'already_delivered': self.already_delivered,
            'failed': self.failed,
            'failure_codes': [f.code or 'UNKNOWN' for f in self.failures],
        }


def business_today() -> date:
    return meal_off_business_now(get_meal_off_settings()).date()


def eligible_delivery_queryset(service_date: date, meal_period: str):
    if meal_period not in VALID_MEAL_PERIODS:
        raise ValueError(f'Invalid meal_period: {meal_period}')
    from django.db.models import Q

    return (
        OrderDelivery.objects.filter(
            service_date=service_date,
            meal_period=meal_period,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )
        .filter(live_delivery_q(service_date))
        .exclude(
            Q(subscription__customer__meal_service_blocked_low_balance=True)
            | Q(order__customer__meal_service_blocked_low_balance=True)
        )
        .select_related(
            'order',
            'order__customer',
            'order__customer__user',
            'subscription',
            'subscription__customer',
            'subscription__customer__user',
        )
        .order_by('id')
    )


def _lock_path(meal_period: str) -> Path:
    base = Path(getattr(settings, 'BASE_DIR', Path.cwd()))
    return base / 'tmp' / 'locks' / f'auto_deliver_{meal_period}.lock'


@contextmanager
def auto_delivery_process_lock(meal_period: str):
    """Non-blocking exclusive lock so overlapping cron runs exit cleanly."""
    path = _lock_path(meal_period)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, 'a+b')
    locked = False
    try:
        if sys.platform == 'win32':
            import msvcrt

            fh.seek(0)
            if fh.read(1) == b'':
                fh.write(b'0')
                fh.flush()
            fh.seek(0)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
            except OSError as exc:
                raise AutoDeliveryLockError(
                    f'Auto-delivery lock busy for meal_period={meal_period}'
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except BlockingIOError as exc:
                raise AutoDeliveryLockError(
                    f'Auto-delivery lock busy for meal_period={meal_period}'
                ) from exc
        yield
    finally:
        if locked:
            try:
                if sys.platform == 'win32':
                    import msvcrt

                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                logger.exception('Failed to release auto-delivery lock path=%s', path)
        fh.close()


def run_auto_delivery(
    *,
    service_date: date | None = None,
    meal_period: str,
    dry_run: bool = False,
    acquire_lock: bool = True,
) -> AutoDeliveryRunResult:
    if meal_period not in VALID_MEAL_PERIODS:
        raise ValueError(f'Invalid meal_period: {meal_period}')

    target_date = service_date or business_today()
    result = AutoDeliveryRunResult(
        service_date=target_date,
        meal_period=meal_period,
        dry_run=dry_run,
    )

    if not getattr(settings, 'AUTO_MEAL_DELIVERY_ENABLED', True):
        result.disabled = True
        logger.info('Auto meal delivery disabled by settings: %s', result.as_log_dict())
        return result

    def _execute() -> AutoDeliveryRunResult:
        qs = eligible_delivery_queryset(target_date, meal_period)
        # Materialize PKs first so per-slot work does not hold a huge queryset.
        delivery_ids = list(qs.values_list('id', flat=True))
        result.candidate_count = len(delivery_ids)

        if dry_run:
            logger.info('Auto meal delivery dry-run: %s', result.as_log_dict())
            return result

        note = f'Auto-delivered by cron ({meal_period})'
        for delivery_id in delivery_ids:
            delivery = OrderDelivery.objects.select_related(
                'order',
                'order__customer',
                'order__customer__user',
                'subscription',
                'subscription__customer',
                'subscription__customer__user',
            ).get(pk=delivery_id)
            before_status = delivery.status
            result.attempted += 1
            try:
                updated = mark_delivery_and_notify(
                    delivery,
                    OrderDelivery.DeliveryStatus.DELIVERED,
                    marked_by=None,
                    note=note,
                )
            except DeliveryError as exc:
                result.failed += 1
                result.failures.append(
                    SlotFailure(
                        delivery_public_id=str(delivery.public_id),
                        code=getattr(exc, 'code', None),
                        message=str(exc),
                    )
                )
                logger.warning(
                    'Auto-delivery failed delivery_id=%s public_id=%s code=%s detail=%s',
                    delivery.pk,
                    delivery.public_id,
                    getattr(exc, 'code', None),
                    exc,
                )
                continue
            except Exception:
                result.failed += 1
                result.failures.append(
                    SlotFailure(
                        delivery_public_id=str(delivery.public_id),
                        code='UNEXPECTED',
                        message='Unexpected error during auto-delivery',
                    )
                )
                logger.exception(
                    'Unexpected auto-delivery error delivery_id=%s public_id=%s',
                    delivery.pk,
                    delivery.public_id,
                )
                continue

            if before_status == OrderDelivery.DeliveryStatus.DELIVERED:
                result.already_delivered += 1
            elif updated.status == OrderDelivery.DeliveryStatus.DELIVERED:
                result.delivered += 1
            else:
                result.failed += 1
                result.failures.append(
                    SlotFailure(
                        delivery_public_id=str(updated.public_id),
                        code='UNEXPECTED_STATUS',
                        message=f'Expected delivered, got {updated.status}',
                    )
                )

        logger.info('Auto meal delivery finished: %s', result.as_log_dict())
        return result

    if not acquire_lock:
        return _execute()

    try:
        with auto_delivery_process_lock(meal_period):
            return _execute()
    except AutoDeliveryLockError:
        result.lock_busy = True
        logger.warning('Auto meal delivery lock busy: %s', result.as_log_dict())
        return result
