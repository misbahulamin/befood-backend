"""Delivery-fee collection reporting aggregates and cohort lists."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import CharField, Count, F, QuerySet, Sum, Value
from django.db.models.functions import Coalesce, Concat, Lower, Trim

from orders.models import CustomerSubscription
from user_management.services.admin_people_search import build_customer_people_q
from wallet.models import DeliveryFeePayment
from wallet.services.delivery_fee import DeliveryFeePeriodError, _admin_display, _validate_period


COHORT_PAID = 'paid'
COHORT_PENDING = 'pending'
VALID_COHORTS = frozenset({COHORT_PAID, COHORT_PENDING})


def paid_payments_qs(*, year: int, month: int) -> QuerySet[DeliveryFeePayment]:
    """Paid delivery-fee payments for a billing period."""
    month, year = _validate_period(month, year)
    return DeliveryFeePayment.objects.filter(
        payment_year=year,
        payment_month=month,
        status=DeliveryFeePayment.Status.PAID,
    )


def paid_customer_ids_for_period(*, year: int, month: int):
    """Distinct customer PKs with a paid fee for the period."""
    return paid_payments_qs(year=year, month=month).values_list('customer_id', flat=True).distinct()


def pending_active_subscriber_qs(*, year: int, month: int) -> QuerySet[CustomerSubscription]:
    """
    Active subscriptions whose customer has no paid delivery fee for the period.

    One active subscription per customer is enforced by DB constraint.
    """
    month, year = _validate_period(month, year)
    paid_ids = paid_customer_ids_for_period(year=year, month=month)
    return CustomerSubscription.objects.filter(
        status=CustomerSubscription.Status.ACTIVE,
    ).exclude(customer_id__in=paid_ids)


def monthly_delivery_fee_report(*, year: int, month: int) -> dict:
    month, year = _validate_period(month, year)
    paid_qs = paid_payments_qs(year=year, month=month)
    aggregates = paid_qs.aggregate(
        total_collected=Sum('amount'),
        customers_paid=Count('customer_id', distinct=True),
    )
    total_collected = aggregates['total_collected'] or Decimal('0.00')
    customers_paid = aggregates['customers_paid'] or 0
    pending_customers = pending_active_subscriber_qs(year=year, month=month).count()

    return {
        'year': year,
        'month': month,
        'total_collected': f'{Decimal(total_collected).quantize(Decimal("0.01")):.2f}',
        'customers_paid': customers_paid,
        'pending_customers': pending_customers,
    }


def lifetime_delivery_fee_report() -> dict:
    aggregates = DeliveryFeePayment.objects.filter(
        status=DeliveryFeePayment.Status.PAID,
    ).aggregate(
        total_collected=Sum('amount'),
        customers_paid=Count('customer_id', distinct=True),
    )
    total_collected = aggregates['total_collected'] or Decimal('0.00')
    customers_paid = aggregates['customers_paid'] or 0
    return {
        'total_collected': f'{Decimal(total_collected).quantize(Decimal("0.01")):.2f}',
        'customers_paid': customers_paid,
    }


def parse_report_year_month(query_params) -> tuple[int, int]:
    year_raw = query_params.get('year')
    month_raw = query_params.get('month')
    if year_raw is None or month_raw is None:
        raise DeliveryFeePeriodError('year and month query parameters are required.')
    return _validate_period(month_raw, year_raw)


def parse_cohort(value) -> str:
    cohort = (value or '').strip().lower()
    if cohort not in VALID_COHORTS:
        raise DeliveryFeePeriodError(
            f'cohort must be one of: {", ".join(sorted(VALID_COHORTS))}.'
        )
    return cohort


def _customer_sort_name_annotation(*, customer_prefix: str = 'customer__') -> Lower:
    first = f'{customer_prefix}user__first_name'
    last = f'{customer_prefix}user__last_name'
    email = f'{customer_prefix}user__email'
    char = CharField()
    return Lower(
        Coalesce(
            Trim(
                Concat(
                    F(first),
                    Value(' '),
                    F(last),
                    output_field=char,
                )
            ),
            F(email),
            Value(''),
            output_field=char,
        )
    )


def list_monthly_delivery_fee_customers(
    *,
    year: int,
    month: int,
    cohort: str,
    q: str | None = None,
) -> QuerySet:
    """
    Ordered queryset for paid (DeliveryFeePayment) or pending (CustomerSubscription) cohorts.

    Optional `q` narrows by customer name/phone (allowlisted people search).
    """
    month, year = _validate_period(month, year)
    cohort = parse_cohort(cohort)
    search = (q or '').strip()

    if cohort == COHORT_PAID:
        qs = (
            paid_payments_qs(year=year, month=month)
            .select_related(
                'customer__user',
                'deducted_by_admin__user',
            )
            .annotate(sort_name=_customer_sort_name_annotation())
        )
        if search:
            qs = qs.filter(build_customer_people_q(search, customer_prefix='customer__'))
        return qs.order_by('-created_at', 'sort_name', 'id')

    qs = (
        pending_active_subscriber_qs(year=year, month=month)
        .select_related('customer__user', 'customer__wallet', 'meal')
        .annotate(sort_name=_customer_sort_name_annotation())
    )
    if search:
        qs = qs.filter(build_customer_people_q(search, customer_prefix='customer__'))
    return qs.order_by(F('sort_name').asc(nulls_last=True), 'customer__phone', 'id')


def serialize_paid_cohort_row(payment: DeliveryFeePayment) -> dict:
    from user_management.services.admin_customer import _display_name

    customer = payment.customer
    return {
        'customer_public_id': str(customer.public_id),
        'customer_name': _display_name(customer),
        'customer_phone': customer.phone or None,
        'amount': f'{payment.amount.quantize(Decimal("0.01")):.2f}',
        'paid_at': payment.created_at,
        'created_at': payment.created_at,
        'deducted_by_admin': _admin_display(payment.deducted_by_admin) or None,
        'payment_public_id': str(payment.public_id),
    }


def serialize_pending_cohort_row(subscription: CustomerSubscription) -> dict:
    from user_management.services.admin_customer import _display_name
    from wallet.models import Wallet

    customer = subscription.customer
    try:
        wallet = customer.wallet
    except Wallet.DoesNotExist:
        wallet = None

    return {
        'customer_public_id': str(customer.public_id),
        'customer_name': _display_name(customer),
        'customer_phone': customer.phone or None,
        'wallet_balance': (
            f'{wallet.balance.quantize(Decimal("0.01")):.2f}' if wallet is not None else None
        ),
        'wallet_status': wallet.status if wallet is not None else None,
        'package_name': subscription.meal_name_snapshot or None,
        'subscription_status': subscription.status,
    }


def serialize_cohort_row(*, cohort: str, row) -> dict:
    if cohort == COHORT_PAID:
        return serialize_paid_cohort_row(row)
    return serialize_pending_cohort_row(row)
