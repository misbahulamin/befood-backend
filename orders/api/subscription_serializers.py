from rest_framework import serializers

from meals.models import MealCategory
from meals.services.meal_image import validate_image_extension, validate_image_size
from meals.services.meal_offering import resolve_public_per_meal_price
from orders.models import CustomerSubscription, OrderDelivery
from orders.services.meal_off import can_meal_off, can_meal_on, meal_off_deadline
from orders.services.order_service import FrozenWalletOrderError, InsufficientWalletBalanceError
from orders.services.subscription_service import (
    AlreadySubscribedError,
    PlanUnavailableError,
    SubscriptionError,
    cancel_subscription,
    get_subscription_progress,
    resolve_effective_meal_period,
    normalize_subscription_quantity,
    subscribe_customer,
)
from wallet.services.subscription_delivery_fee import (
    SubscriptionDeliveryFeeError,
    calculate_subscription_delivery_fee,
    format_fee_summary,
)
from user_management.validators import format_bd_phone_e164


class CustomerSubscriptionPlanSerializer(serializers.ModelSerializer):
    meal_thumbnail = serializers.SerializerMethodField()
    per_meal_price = serializers.SerializerMethodField()
    pricing_status = serializers.CharField(read_only=True)

    class Meta:
        model = MealCategory
        fields = (
            'public_id',
            'meal_name',
            'description',
            'meal_thumbnail',
            'meal_period',
            'total_price',
            'per_meal_price',
            'pricing_status',
            'is_active',
            'is_subscribable',
        )
        read_only_fields = fields

    def get_meal_thumbnail(self, obj):
        if not obj.meal_thumbnail:
            return None
        request = self.context.get('request')
        url = obj.meal_thumbnail.url
        return request.build_absolute_uri(url) if request else url

    def get_per_meal_price(self, obj):
        return resolve_public_per_meal_price(obj)


class AdminSubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealCategory
        fields = (
            'public_id',
            'meal_name',
            'description',
            'meal_thumbnail',
            'meal_period',
            'meal_type',
            'total_price',
            'is_active',
            'is_subscribable',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('public_id', 'total_price', 'created_at', 'updated_at')
        extra_kwargs = {
            'meal_period': {'required': True},
            'meal_thumbnail': {'required': True},
            'meal_type': {'required': False},
        }

    def validate_meal_thumbnail(self, value):
        if value is None:
            return value
        try:
            validate_image_extension(value.name)
            validate_image_size(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def create(self, validated_data):
        validated_data.setdefault('is_subscribable', True)
        validated_data.setdefault('meal_type', MealCategory.MealType.MONTHLY)
        validated_data['total_price'] = None
        return super().create(validated_data)


class SubscribeSerializer(serializers.Serializer):
    plan_public_id = serializers.UUIDField()
    customer_note = serializers.CharField(required=False, allow_blank=True, default='')
    meal_preference = serializers.ChoiceField(
        choices=[('lunch', 'lunch'), ('dinner', 'dinner'), ('both', 'both')],
        required=False,
        allow_null=True,
    )
    quantity = serializers.IntegerField(required=False, min_value=1, default=1)

    def validate_plan_public_id(self, value):
        try:
            meal = MealCategory.objects.get(public_id=value)
        except MealCategory.DoesNotExist:
            raise serializers.ValidationError('Meal plan not found.')
        self.context['meal'] = meal
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        profile = getattr(user, 'customer_profile', None)
        if profile is None:
            raise serializers.ValidationError('Customer profile is required to subscribe.')
        from user_management.services.identity_verification import (
            IDENTITY_VERIFICATION_REQUIRED_SUBSCRIBE_MESSAGE,
            is_customer_identity_verified,
        )

        if not is_customer_identity_verified(user):
            raise serializers.ValidationError(IDENTITY_VERIFICATION_REQUIRED_SUBSCRIBE_MESSAGE)
        meal = self.context['meal']
        try:
            return subscribe_customer(
                profile,
                meal,
                customer_note=validated_data.get('customer_note', ''),
                meal_preference=validated_data.get('meal_preference'),
                quantity=validated_data.get('quantity', 1),
            )
        except AlreadySubscribedError as exc:
            raise serializers.ValidationError(
                {'non_field_errors': [str(exc)], 'error_code': [exc.code]}
            )
        except PlanUnavailableError as exc:
            raise serializers.ValidationError({'plan_public_id': [str(exc)]})
        except SubscriptionError as exc:
            field = (
                'meal_preference'
                if getattr(exc, 'code', '') in {'INVALID_MEAL_PREFERENCE', 'MEAL_PREFERENCE_REQUIRED', 'MEAL_PREFERENCE_NOT_SUPPORTED'}
                else 'quantity' if getattr(exc, 'code', '') == 'INVALID_QUANTITY' else 'non_field_errors'
            )
            payload = {'error_code': [exc.code]} if getattr(exc, 'code', None) else {}
            payload[field] = [str(exc)]
            raise serializers.ValidationError(payload)
        except (InsufficientWalletBalanceError, FrozenWalletOrderError) as exc:
            raise serializers.ValidationError({'non_field_errors': [str(exc)]})


class SubscriptionDeliverySerializer(serializers.ModelSerializer):
    can_meal_off = serializers.SerializerMethodField()
    can_meal_on = serializers.SerializerMethodField()
    meal_off_deadline_at = serializers.SerializerMethodField()

    class Meta:
        model = OrderDelivery
        fields = (
            'public_id',
            'service_date',
            'meal_period',
            'status',
            'skip_source',
            'payment_status',
            'charged_amount',
            'can_meal_off',
            'can_meal_on',
            'meal_off_deadline_at',
            'delivery_label_snapshot',
            'delivery_full_address_snapshot',
            'marked_at',
            'note',
        )
        read_only_fields = fields

    def get_can_meal_off(self, obj):
        return can_meal_off(obj)

    def get_can_meal_on(self, obj):
        return can_meal_on(obj)

    def get_meal_off_deadline_at(self, obj):
        try:
            deadline = meal_off_deadline(obj.service_date, obj.meal_period)
        except ValueError:
            return None
        return deadline.isoformat().replace('+00:00', 'Z')


class SubscriptionProgressMixin:
    def _progress(self, obj):
        cache = self.context.setdefault('_subscription_progress_cache', {})
        if obj.pk not in cache:
            cache[obj.pk] = get_subscription_progress(obj)
        return cache[obj.pk]

    def get_expected_deliveries(self, obj):
        return self._progress(obj)['expected_deliveries']

    def get_delivered_count(self, obj):
        return self._progress(obj)['delivered_count']

    def get_remaining_count(self, obj):
        return self._progress(obj)['remaining_count']

    def get_active_days_this_month(self, obj):
        return self._progress(obj)['active_days_this_month']


class SubscriptionFeeSummaryMixin(serializers.Serializer):
    monthly_delivery_fee = serializers.SerializerMethodField()
    fee_rule_code = serializers.SerializerMethodField()

    def _fee_summary(self, obj):
        cache = self.context.setdefault('_subscription_fee_cache', {})
        if obj.pk not in cache:
            try:
                cache[obj.pk] = format_fee_summary(
                    calculate_subscription_delivery_fee(
                        obj.meal_period_snapshot, getattr(obj, 'quantity', 1) or 1
                    )
                )
            except SubscriptionDeliveryFeeError:
                cache[obj.pk] = {
                    'meal_period': obj.meal_period_snapshot,
                    'quantity': getattr(obj, 'quantity', 1) or 1,
                    'monthly_delivery_fee': None,
                    'fee_rule_code': None,
                }
        return cache[obj.pk]

    def get_monthly_delivery_fee(self, obj):
        return self._fee_summary(obj)['monthly_delivery_fee']

    def get_fee_rule_code(self, obj):
        return self._fee_summary(obj)['fee_rule_code']


class CustomerSubscriptionSerializer(SubscriptionProgressMixin, SubscriptionFeeSummaryMixin, serializers.ModelSerializer):
    plan_public_id = serializers.UUIDField(source='meal.public_id', read_only=True)
    expected_deliveries = serializers.SerializerMethodField()
    delivered_count = serializers.SerializerMethodField()
    remaining_count = serializers.SerializerMethodField()
    active_days_this_month = serializers.SerializerMethodField()

    class Meta:
        model = CustomerSubscription
        fields = (
            'public_id',
            'plan_public_id',
            'meal_name_snapshot',
            'meal_period_snapshot',
            'quantity',
            'monthly_delivery_fee',
            'fee_rule_code',
            'status',
            'started_on',
            'cancelled_at',
            'cancel_effective_on',
            'expected_deliveries',
            'delivered_count',
            'remaining_count',
            'active_days_this_month',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class SubscriptionQuoteSerializer(serializers.Serializer):
    plan_public_id = serializers.UUIDField()
    meal_preference = serializers.ChoiceField(
        choices=[('lunch', 'lunch'), ('dinner', 'dinner'), ('both', 'both')],
        required=False,
        allow_null=True,
    )
    quantity = serializers.IntegerField(required=False, min_value=1, default=1)

    def validate(self, attrs):
        try:
            meal = MealCategory.objects.get(public_id=attrs['plan_public_id'])
        except MealCategory.DoesNotExist:
            raise serializers.ValidationError({'plan_public_id': ['Meal plan not found.']})
        if not meal.is_active or not meal.is_subscribable:
            raise serializers.ValidationError({'plan_public_id': ['This meal plan is not available to subscribe.']})
        try:
            effective, used_fallback = resolve_effective_meal_period(
                meal, attrs.get('meal_preference'), allow_fallback=True
            )
            qty = normalize_subscription_quantity(attrs.get('quantity', 1))
            summary = format_fee_summary(
                calculate_subscription_delivery_fee(effective, qty)
            )
        except SubscriptionError as exc:
            raise serializers.ValidationError({'meal_preference': [str(exc)]})
        except SubscriptionDeliveryFeeError as exc:
            raise serializers.ValidationError({'quantity': [str(exc)]})
        attrs['meal'] = meal
        attrs['effective_meal_period'] = effective
        attrs['used_fallback'] = used_fallback
        attrs['fee_summary'] = summary
        return attrs


class CustomerSubscriptionDetailSerializer(CustomerSubscriptionSerializer):
    deliveries = SubscriptionDeliverySerializer(many=True, read_only=True)

    class Meta(CustomerSubscriptionSerializer.Meta):
        fields = CustomerSubscriptionSerializer.Meta.fields + ('deliveries', 'customer_note')


class AdminSubscriptionListSerializer(CustomerSubscriptionSerializer):
    customer_email = serializers.EmailField(source='customer.user.email', read_only=True)
    customer_public_id = serializers.UUIDField(
        source='customer.public_id', read_only=True, allow_null=True
    )
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()

    class Meta(CustomerSubscriptionSerializer.Meta):
        fields = CustomerSubscriptionSerializer.Meta.fields + (
            'customer_email',
            'customer_public_id',
            'customer_name',
            'customer_phone',
        )

    def get_customer_name(self, obj):
        user = obj.customer.user
        return f'{user.first_name} {user.last_name}'.strip() or user.email

    def get_customer_phone(self, obj):
        return format_bd_phone_e164(obj.customer.phone)


class AdminSubscriptionDetailSerializer(AdminSubscriptionListSerializer):
    deliveries = SubscriptionDeliverySerializer(many=True, read_only=True)

    class Meta(AdminSubscriptionListSerializer.Meta):
        fields = AdminSubscriptionListSerializer.Meta.fields + ('deliveries', 'customer_note')


class CancelSubscriptionSerializer(serializers.Serializer):
    def save(self, **kwargs):
        subscription = self.context['subscription']
        return cancel_subscription(subscription)
