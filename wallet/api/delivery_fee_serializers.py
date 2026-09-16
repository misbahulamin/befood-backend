"""Serializers for admin delivery-fee deduction APIs."""

from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from wallet.services.ledger import MAX_FUNDING_AMOUNT, MIN_FUNDING_AMOUNT


def _validate_fee_amount(value: Decimal) -> Decimal:
    if value is None:
        raise serializers.ValidationError('Amount is required.')
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise serializers.ValidationError('Amount must be a valid decimal number.') from exc
    if amount <= 0:
        raise serializers.ValidationError('Amount must be greater than zero.')
    if amount < MIN_FUNDING_AMOUNT:
        raise serializers.ValidationError(f'Amount must be at least {MIN_FUNDING_AMOUNT}.')
    if amount > MAX_FUNDING_AMOUNT:
        raise serializers.ValidationError(f'Amount must not exceed {MAX_FUNDING_AMOUNT}.')
    if amount.as_tuple().exponent < -2:
        raise serializers.ValidationError('Amount must have at most 2 decimal places.')
    return amount.quantize(Decimal('0.01'))


class DeliveryFeeChargeSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_month = serializers.IntegerField(min_value=1, max_value=12)
    payment_year = serializers.IntegerField(min_value=2000, max_value=2100)
    reason = serializers.CharField(max_length=255)
    idempotency_key = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
    )

    def validate_amount(self, value: Decimal) -> Decimal:
        return _validate_fee_amount(value)

    def validate_reason(self, value: str) -> str:
        cleaned = (value or '').strip()
        if not cleaned:
            raise serializers.ValidationError('reason is required.')
        return cleaned

    def validate_idempotency_key(self, value):
        if value is None or value == '':
            return None
        return value


class DeliveryFeePaymentSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    customer_public_id = serializers.UUIDField(required=False)
    amount = serializers.CharField()
    payment_month = serializers.IntegerField()
    payment_year = serializers.IntegerField()
    period_label = serializers.CharField()
    status = serializers.CharField()
    reason = serializers.CharField()
    source = serializers.CharField()
    deducted_by_admin = serializers.CharField(allow_null=True)
    deducted_by_admin_id = serializers.IntegerField(allow_null=True, required=False)
    wallet_transaction_public_id = serializers.UUIDField()
    wallet_balance_after = serializers.CharField(allow_null=True, required=False)
    created_at = serializers.DateTimeField()
    paid_at = serializers.DateTimeField()


class DeliveryFeeContextSerializer(serializers.Serializer):
    customer_public_id = serializers.UUIDField()
    customer_name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)
    phone_display = serializers.CharField(allow_blank=True)
    wallet_balance = serializers.CharField()
    recharge_balance = serializers.CharField()
    commission_balance = serializers.CharField()
    wallet_status = serializers.CharField()
    wallet_currency = serializers.CharField()
    active_subscription = serializers.DictField(allow_null=True)
    current_month_delivery_fee_paid = serializers.CharField()
    delivery_fee_history = DeliveryFeePaymentSerializer(many=True)


class DeliveryFeeMonthlyReportSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    total_collected = serializers.CharField()
    customers_paid = serializers.IntegerField()
    pending_customers = serializers.IntegerField()


class DeliveryFeeLifetimeReportSerializer(serializers.Serializer):
    total_collected = serializers.CharField()
    customers_paid = serializers.IntegerField()
