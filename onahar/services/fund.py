from django.db import transaction
from django.db.models import F

from onahar.models import OnaharFundLedgerEntry, OnaharSettings
from onahar.services.audit import write_audit


class OnaharFundError(Exception):
    def __init__(self, message: str, code: str = 'ONAHAR_FUND_ERROR'):
        super().__init__(message)
        self.code = code


class InsufficientOnaharFundError(OnaharFundError):
    def __init__(self, message: str = 'Insufficient Onahar fund meals.'):
        super().__init__(message, code='INSUFFICIENT_ONAHAR_FUND')


def get_or_create_settings() -> OnaharSettings:
    settings_obj, _ = OnaharSettings.objects.get_or_create(
        pk=1,
        defaults={'contribution_target': 50},
    )
    return settings_obj


@transaction.atomic
def lock_settings() -> OnaharSettings:
    get_or_create_settings()
    return OnaharSettings.objects.select_for_update().get(pk=1)


def available_meals() -> int:
    return get_or_create_settings().available_meals


def _apply_ledger(
    *,
    direction: str,
    meals: int,
    entry_type: str,
    contribution=None,
    distribution=None,
    note: str = '',
    actor=None,
    audit_action: str | None = None,
) -> OnaharFundLedgerEntry:
    if meals < 1:
        raise OnaharFundError('Ledger meals must be >= 1.')

    settings_obj = lock_settings()
    if direction == OnaharFundLedgerEntry.Direction.CREDIT:
        settings_obj.available_meals = F('available_meals') + meals
        if entry_type in {
            OnaharFundLedgerEntry.EntryType.CONTRIBUTION,
            OnaharFundLedgerEntry.EntryType.DISTRIBUTION_RESTORE,
        }:
            if entry_type == OnaharFundLedgerEntry.EntryType.CONTRIBUTION:
                settings_obj.total_contributed_meals = F('total_contributed_meals') + meals
            else:
                settings_obj.total_distributed_meals = F('total_distributed_meals') - meals
        elif entry_type == OnaharFundLedgerEntry.EntryType.CONTRIBUTION_ADJUSTMENT:
            # Compensating credit rarely used; treat as contributed increase.
            settings_obj.total_contributed_meals = F('total_contributed_meals') + meals
        settings_obj.save()
    else:
        settings_obj.refresh_from_db()
        if (
            entry_type == OnaharFundLedgerEntry.EntryType.DISTRIBUTION
            and settings_obj.available_meals < meals
        ):
            raise InsufficientOnaharFundError(
                f'Requested {meals} meals but only {settings_obj.available_meals} available.'
            )
        settings_obj.available_meals = F('available_meals') - meals
        if entry_type == OnaharFundLedgerEntry.EntryType.DISTRIBUTION:
            settings_obj.total_distributed_meals = F('total_distributed_meals') + meals
        elif entry_type == OnaharFundLedgerEntry.EntryType.CONTRIBUTION_ADJUSTMENT:
            settings_obj.total_contributed_meals = F('total_contributed_meals') - meals
        settings_obj.save()

    settings_obj.refresh_from_db()
    # Clamp distributed from going below zero on restore race
    if settings_obj.total_distributed_meals < 0:
        OnaharSettings.objects.filter(pk=settings_obj.pk).update(total_distributed_meals=0)
        settings_obj.refresh_from_db()

    entry = OnaharFundLedgerEntry.objects.create(
        direction=direction,
        meals=meals,
        entry_type=entry_type,
        balance_after=settings_obj.available_meals,
        contribution=contribution,
        distribution=distribution,
        note=note,
    )
    if audit_action:
        write_audit(
            action=audit_action,
            actor=actor,
            new_value={
                'meals': meals,
                'direction': direction,
                'entry_type': entry_type,
                'balance_after': entry.balance_after,
                'ledger_public_id': str(entry.public_id),
            },
            metadata={
                'contribution_id': contribution.pk if contribution else None,
                'distribution_id': distribution.pk if distribution else None,
            },
        )
    return entry


def credit_fund(
    *,
    meals: int,
    entry_type: str,
    contribution=None,
    distribution=None,
    note: str = '',
    actor=None,
    audit_action: str | None = 'fund_credited',
) -> OnaharFundLedgerEntry:
    return _apply_ledger(
        direction=OnaharFundLedgerEntry.Direction.CREDIT,
        meals=meals,
        entry_type=entry_type,
        contribution=contribution,
        distribution=distribution,
        note=note,
        actor=actor,
        audit_action=audit_action,
    )


def debit_fund(
    *,
    meals: int,
    entry_type: str,
    contribution=None,
    distribution=None,
    note: str = '',
    actor=None,
    audit_action: str | None = 'fund_deducted',
    enforce_available: bool = True,
) -> OnaharFundLedgerEntry:
    if not enforce_available and entry_type == OnaharFundLedgerEntry.EntryType.DISTRIBUTION:
        # Still use normal path; flag reserved for future override.
        pass
    return _apply_ledger(
        direction=OnaharFundLedgerEntry.Direction.DEBIT,
        meals=meals,
        entry_type=entry_type,
        contribution=contribution,
        distribution=distribution,
        note=note,
        actor=actor,
        audit_action=audit_action,
    )


def fund_summary() -> dict:
    s = get_or_create_settings()
    return {
        'total_contributed_meals': s.total_contributed_meals,
        'total_distributed_meals': s.total_distributed_meals,
        'available_meals': s.available_meals,
        'contribution_target': s.contribution_target,
    }
