from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from orders.services.meal_payment import MEAL_DELIVERY_PURPOSE
from orders.services.order_wallet_settings import get_order_wallet_settings
from wallet.models import Wallet, WalletTransaction
from wallet.services.funding import PROVIDER_RECHARGE_METHODS, sanitize_transaction_id
from wallet.services.ledger import MAX_FUNDING_AMOUNT, MIN_FUNDING_AMOUNT


class MealPaymentInfoSerializer(serializers.Serializer):
    meal_name = serializers.CharField(allow_null=True)
    service_date = serializers.CharField(allow_null=True)
    meal_period = serializers.CharField(allow_null=True)
    order_public_id = serializers.CharField(allow_null=True)
    subscription_public_id = serializers.CharField(allow_null=True, required=False)
    delivery_public_id = serializers.CharField(allow_null=True)
    final_meal_price = serializers.CharField(allow_null=True, required=False)
    charge_source = serializers.CharField(allow_null=True, required=False)


class WalletSerializer(serializers.ModelSerializer):
    min_wallet_balance_to_order = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = (
            'public_id',
            'balance',
            'currency',
            'status',
            'min_wallet_balance_to_order',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_min_wallet_balance_to_order(self, obj):
        amount = get_order_wallet_settings().min_wallet_balance_to_order.quantize(Decimal('0.01'))
        return f'{amount:.2f}'


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Customer-facing ledger row (no reviewer identity)."""

    meal_payment = serializers.SerializerMethodField()
    transaction_id = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = (
            'public_id',
            'type',
            'direction',
            'amount',
            'balance_after',
            'status',
            'method',
            'transaction_id',
            'note',
            'reviewed_at',
            'rejection_reason',
            'meal_payment',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_transaction_id(self, obj):
        if obj.type == WalletTransaction.Type.RECHARGE and obj.external_ref:
            return obj.external_ref
        return None

    def get_meal_payment(self, obj):
        if obj.type != WalletTransaction.Type.PAYMENT:
            return None
        metadata = obj.metadata or {}
        if metadata.get('purpose') != MEAL_DELIVERY_PURPOSE:
            return None
        return {
            'meal_name': metadata.get('meal_name'),
            'service_date': metadata.get('service_date'),
            'meal_period': metadata.get('meal_period'),
            'order_public_id': metadata.get('order_public_id'),
            'subscription_public_id': metadata.get('subscription_public_id'),
            'delivery_public_id': metadata.get('delivery_public_id'),
            'final_meal_price': metadata.get('final_meal_price'),
            'charge_source': metadata.get('charge_source'),
        }


def _validate_funding_amount(value: Decimal) -> Decimal:
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


class RechargeRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.CharField(max_length=20)
    transaction_id = serializers.CharField(max_length=255)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    idempotency_key = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
    )

    def validate_amount(self, value: Decimal) -> Decimal:
        return _validate_funding_amount(value)

    def validate_payment_method(self, value: str) -> str:
        normalized = (value or '').strip().lower()
        if normalized not in PROVIDER_RECHARGE_METHODS:
            raise serializers.ValidationError(
                'payment_method must be one of: bkash, nagad, bank.'
            )
        return normalized

    def validate_transaction_id(self, value: str) -> str:
        sanitized = sanitize_transaction_id(value)
        if not sanitized:
            raise serializers.ValidationError('transaction_id is required.')
        return sanitized

    def validate_idempotency_key(self, value):
        if value is None or value == '':
            return None
        return value


class WithdrawRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    idempotency_key = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
    )

    def validate_amount(self, value: Decimal) -> Decimal:
        return _validate_funding_amount(value)

    def validate_idempotency_key(self, value):
        if value is None or value == '':
            return None
        return value


class FundingResponseSerializer(serializers.Serializer):
    wallet = WalletSerializer()
    transaction = WalletTransactionSerializer()


class FundingRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default='',
    )


class AdminFundingRequestSerializer(serializers.ModelSerializer):
    transaction_id = serializers.SerializerMethodField()
    customer_public_id = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    reviewed_by_email = serializers.SerializerMethodField()
    reviewed_by_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = WalletTransaction
        fields = (
            'public_id',
            'type',
            'direction',
            'amount',
            'balance_after',
            'status',
            'method',
            'transaction_id',
            'note',
            'customer_public_id',
            'customer_email',
            'customer_name',
            'reviewed_by_id',
            'reviewed_by_email',
            'reviewed_at',
            'rejection_reason',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_transaction_id(self, obj):
        if obj.type == WalletTransaction.Type.RECHARGE:
            return obj.external_ref or None
        return None

    def get_customer_public_id(self, obj):
        return str(obj.wallet.customer.public_id)

    def get_customer_email(self, obj):
        return obj.wallet.customer.user.email

    def get_customer_name(self, obj):
        user = obj.wallet.customer.user
        return (user.get_full_name() or user.username or '').strip()

    def get_reviewed_by_email(self, obj):
        if obj.reviewed_by_id is None:
            return None
        return obj.reviewed_by.email
