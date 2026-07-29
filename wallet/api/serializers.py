from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from orders.services.order_wallet_settings import get_order_wallet_settings
from wallet.models import Wallet, WalletTransaction
from wallet.services.ledger import MAX_FUNDING_AMOUNT, MIN_FUNDING_AMOUNT


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
            'note',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class FundingRequestSerializer(serializers.Serializer):
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

    def validate_idempotency_key(self, value):
        if value is None or value == '':
            return None
        return value


class FundingResponseSerializer(serializers.Serializer):
    wallet = WalletSerializer()
    transaction = WalletTransactionSerializer()
