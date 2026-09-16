"""Delivery-fee collection reporting aggregates."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum

from orders.models import CustomerSubscription
from wallet.models import DeliveryFeePayment
from wallet.services.delivery_fee import DeliveryFeePeriodError, _validate_period


def monthly_delivery_fee_report(*, year: int, month: int) -> dict:
    month, year = _validate_period(month, year)
    paid_qs = DeliveryFeePayment.objects.filter(
        payment_year=year,
        payment_month=month,
        status=DeliveryFeePayment.Status.PAID,
    )
    aggregates = paid_qs.aggregate(
        total_collected=Sum('amount'),
        customers_paid=Count('customer_id', distinct=True),
    )
    total_collected = aggregates['total_collected'] or Decimal('0.00')
    customers_paid = aggregates['customers_paid'] or 0

    paid_customer_ids = paid_qs.values_list('customer_id', flat=True).distinct()
    active_subscriber_count = CustomerSubscription.objects.filter(
        status=CustomerSubscription.Status.ACTIVE,
    ).values('customer_id').distinct().count()
    paid_active_count = (
        CustomerSubscription.objects.filter(
            status=CustomerSubscription.Status.ACTIVE,
            customer_id__in=paid_customer_ids,
        )
        .values('customer_id')
        .distinct()
        .count()
    )
    pending_customers = max(active_subscriber_count - paid_active_count, 0)

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
