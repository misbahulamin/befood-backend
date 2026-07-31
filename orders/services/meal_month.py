"""Meal-month window helpers for advance / future-month ordering."""

from __future__ import annotations

from calendar import month_name
from datetime import date

from django.utils import timezone

# Current month + next 12 months = 13 selectable entries.
MEAL_MONTH_HORIZON_MONTHS = 12

MENU_NOT_PUBLISHED_MESSAGE = (
    "This month's menu has not been published yet. "
    'Once the menu is published, you will be able to place your order.'
)


class MealMonthValidationError(ValueError):
    """Invalid or out-of-window meal month selection."""

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field
        self.message = message


def add_calendar_months(year: int, month: int, delta: int) -> tuple[int, int]:
    index = month - 1 + delta
    return year + index // 12, index % 12 + 1


def format_order_month(year: int, month: int) -> str:
    return f'{year:04d}-{month:02d}'


def month_label(year: int, month: int) -> str:
    return f'{month_name[month]} {year}'


def resolve_optional_year_month(
    year: int | str | None = None,
    month: int | str | None = None,
) -> tuple[int, int] | None:
    """
    Resolve optional paired year/month.

    Both omitted → None (caller uses current-month defaults).
    Both provided → validated (year, month).
    Only one provided → MealMonthValidationError.
    """
    year_provided = year is not None and str(year).strip() != ''
    month_provided = month is not None and str(month).strip() != ''

    if year_provided != month_provided:
        raise MealMonthValidationError(
            'Both year and month are required together.',
            field='year' if year_provided else 'month',
        )

    if not year_provided and not month_provided:
        return None

    try:
        year_int = int(year)
        month_int = int(month)
    except (TypeError, ValueError) as exc:
        raise MealMonthValidationError(
            'Enter a valid year and month (month must be 1–12).',
            field='month',
        ) from exc

    if month_int < 1 or month_int > 12:
        raise MealMonthValidationError('Month must be between 1 and 12.', field='month')
    if year_int < 1:
        raise MealMonthValidationError('Enter a valid year.', field='year')

    return year_int, month_int


def assert_meal_month_in_window(
    year: int,
    month: int,
    *,
    today: date | None = None,
) -> None:
    """Raise if (year, month) is before current local month or more than +12 months ahead."""
    today = today or timezone.localdate()
    current = (today.year, today.month)
    selected = (year, month)
    max_year, max_month = add_calendar_months(today.year, today.month, MEAL_MONTH_HORIZON_MONTHS)

    if selected < current:
        raise MealMonthValidationError(
            'Cannot order for a past month. Select the current month or a future month.',
            field='month',
        )
    if selected > (max_year, max_month):
        raise MealMonthValidationError(
            'Selected month is too far in the future. '
            f'You may order from the current month through {month_label(max_year, max_month)}.',
            field='month',
        )


def iter_orderable_months(*, today: date | None = None):
    """Yield (year, month) for current month through +12 months (13 entries)."""
    today = today or timezone.localdate()
    for offset in range(MEAL_MONTH_HORIZON_MONTHS + 1):
        yield add_calendar_months(today.year, today.month, offset)
