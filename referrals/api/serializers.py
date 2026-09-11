from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from referrals.models import ReferralCommission, ReferralProgramSettings, ReferralRelationship


class ReferralMeSerializer(serializers.Serializer):
    code = serializers.CharField()
    link = serializers.CharField()
    is_usable = serializers.BooleanField()
    share_count = serializers.IntegerField()
    last_shared_at = serializers.DateTimeField(allow_null=True)
    referred_user_count = serializers.IntegerField()
    lifetime_commission = serializers.DecimalField(max_digits=12, decimal_places=2)
    month_commission = serializers.DecimalField(max_digits=12, decimal_places=2)


class ReferredUserSerializer(serializers.ModelSerializer):
    referred_public_id = serializers.UUIDField(source='referred.public_id')
    referred_name = serializers.SerializerMethodField()
    commission_total = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )

    class Meta:
        model = ReferralRelationship
        fields = (
            'public_id',
            'referred_public_id',
            'referred_name',
            'referral_code_used',
            'attributed_at',
            'commission_total',
        )

    def get_referred_name(self, obj):
        user = obj.referred.user
        name = f'{user.first_name} {user.last_name}'.strip()
        return name or user.email or obj.referred.phone or str(obj.referred.public_id)


class ReferralCommissionSerializer(serializers.ModelSerializer):
    """
    Commission list/detail row.

    status_reason values include (non-exhaustive, additive):
    CREDITED, REFERRER_INACTIVE, REFERRED_INACTIVE,
    REFERRER_MEAL_NOT_CONSUMED (retryable skip until referrer delivers same meal),
    AMOUNT_TOO_SMALL, ADMIN_FLOAT_INSUFFICIENT, REVERSED, MANUAL_ADJUSTMENT.
    """

    referred_public_id = serializers.SerializerMethodField()
    delivery_public_id = serializers.SerializerMethodField()

    class Meta:
        model = ReferralCommission
        fields = (
            'public_id',
            'status',
            'status_reason',
            'referred_public_id',
            'delivery_public_id',
            'meal_service_date',
            'meal_period',
            'meal_price',
            'commission_percent',
            'commission_amount',
            'is_manual',
            'created_at',
        )
        extra_kwargs = {
            'status_reason': {
                'help_text': (
                    'Machine reason for status. Includes REFERRER_MEAL_NOT_CONSUMED '
                    'when the referrer has not delivered the same meal/day.'
                ),
            },
        }

    def get_referred_public_id(self, obj):
        return str(obj.referred.public_id) if obj.referred_id else None

    def get_delivery_public_id(self, obj):
        return str(obj.order_delivery.public_id) if obj.order_delivery_id else None


class ValidateReferralCodeSerializer(serializers.Serializer):
    referral_code = serializers.CharField(max_length=16)


class AdminManualAdjustmentSerializer(serializers.Serializer):
    referrer_public_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(max_length=500)
    referred_public_id = serializers.UUIDField(required=False, allow_null=True)


class AdminReverseSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class ReferralProgramSettingsSerializer(serializers.ModelSerializer):
    """Admin GET/PATCH body for live referral commission percent."""

    referral_commission_percent = serializers.DecimalField(
        source='commission_percent',
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.00'),
        max_value=Decimal('100.00'),
    )

    class Meta:
        model = ReferralProgramSettings
        fields = ('referral_commission_percent', 'updated_at')
        read_only_fields = ('updated_at',)

    def validate_referral_commission_percent(self, value):
        try:
            amount = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise serializers.ValidationError(
                'Commission percent must be a valid decimal number.'
            ) from exc
        if amount < 0 or amount > 100:
            raise serializers.ValidationError(
                'Commission percent must be between 0 and 100 inclusive.'
            )
        if amount.as_tuple().exponent < -2:
            raise serializers.ValidationError(
                'Commission percent must have at most 2 decimal places.'
            )
        return amount.quantize(Decimal('0.01'))
