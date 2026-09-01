from rest_framework import serializers

from orders.models import CustomerSubscription, Order, OrderDelivery
from user_management.models import CustomerAddress, CustomerProfile
from user_management.services.admin_customer import (
    build_active_order_payload,
    build_active_subscription_payload,
    build_current_package_summary,
    build_overview_metrics,
    build_wallet_summary,
    get_customer_wallet,
)
from wallet.models import WalletTransaction


class AdminCustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = (
            'public_id',
            'address_type',
            'full_address',
            'city',
            'area',
            'building_name',
            'floor',
            'flat_number',
            'landmark',
            'latitude',
            'longitude',
            'is_default_delivery',
        )
        read_only_fields = fields


class AdminCustomerListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    account_status = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()
    registered_at = serializers.DateTimeField(source='user.date_joined', read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    current_package = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()

    class Meta:
        model = CustomerProfile
        fields = (
            'public_id',
            'name',
            'email',
            'phone',
            'profile_picture_url',
            'is_active',
            'account_status',
            'is_email_verified',
            'verification_status',
            'email_verified_at',
            'registered_at',
            'current_package',
            'wallet_balance',
        )
        read_only_fields = fields

    def get_name(self, obj):
        full = f'{obj.user.first_name} {obj.user.last_name}'.strip()
        return full or obj.user.email

    def get_account_status(self, obj):
        return 'active' if obj.user.is_active else 'inactive'

    def get_verification_status(self, obj):
        return 'verified' if obj.is_email_verified else 'unverified'

    def get_profile_picture_url(self, obj):
        from user_management.services.profile_picture import get_profile_picture_url

        return get_profile_picture_url(obj, request=self.context.get('request'))

    def get_current_package(self, obj):
        return build_current_package_summary(obj)

    def get_wallet_balance(self, obj):
        wallet = get_customer_wallet(obj)
        if wallet is None:
            return None
        return f'{wallet.balance:.2f}'


class AdminCustomerDetailSerializer(AdminCustomerListSerializer):
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    occupation = serializers.CharField(read_only=True)
    gender = serializers.CharField(read_only=True, allow_null=True)
    birth_date = serializers.DateField(read_only=True, allow_null=True)
    is_bachelor = serializers.BooleanField(read_only=True)
    organization_name = serializers.CharField(read_only=True, allow_null=True)
    academic_year_or_position = serializers.CharField(read_only=True, allow_null=True)
    has_allergy = serializers.BooleanField(read_only=True)
    allergy_details = serializers.CharField(read_only=True)
    restricted_foods = serializers.CharField(read_only=True)
    preferred_food_type = serializers.CharField(read_only=True, allow_null=True)
    spice_level = serializers.CharField(read_only=True, allow_null=True)
    religious = serializers.CharField(read_only=True, allow_null=True)
    delivery_instruction = serializers.CharField(read_only=True)
    preferred_delivery_time = serializers.TimeField(read_only=True, allow_null=True)
    profile_completed = serializers.BooleanField(read_only=True)
    profile_completion_percentage = serializers.IntegerField(read_only=True)
    addresses = AdminCustomerAddressSerializer(many=True, read_only=True)
    summary = serializers.SerializerMethodField()
    active_subscription = serializers.SerializerMethodField()
    wallet_summary = serializers.SerializerMethodField()
    active_order = serializers.SerializerMethodField()

    class Meta(AdminCustomerListSerializer.Meta):
        fields = AdminCustomerListSerializer.Meta.fields + (
            'first_name',
            'last_name',
            'occupation',
            'gender',
            'birth_date',
            'is_bachelor',
            'organization_name',
            'academic_year_or_position',
            'has_allergy',
            'allergy_details',
            'restricted_foods',
            'preferred_food_type',
            'spice_level',
            'religious',
            'delivery_instruction',
            'preferred_delivery_time',
            'profile_completed',
            'profile_completion_percentage',
            'addresses',
            'summary',
            'active_subscription',
            'wallet_summary',
            'active_order',
            'created_at',
            'updated_at',
        )

    def get_summary(self, obj):
        return build_overview_metrics(obj)

    def get_active_subscription(self, obj):
        return build_active_subscription_payload(obj)

    def get_wallet_summary(self, obj):
        return build_wallet_summary(obj)

    def get_active_order(self, obj):
        return build_active_order_payload(obj)


class AdminCustomerActiveSubscriptionSerializer(serializers.Serializer):
    active_subscription = serializers.JSONField(allow_null=True)


class AdminCustomerActiveOrderSerializer(serializers.Serializer):
    active_order = serializers.JSONField(allow_null=True)


class AdminCustomerWalletOverviewSerializer(serializers.Serializer):
    wallet_overview = serializers.JSONField()


class AdminCustomerSubscriptionHistorySerializer(serializers.ModelSerializer):
    meal_public_id = serializers.UUIDField(source='meal.public_id', read_only=True)
    delivered_count = serializers.IntegerField(read_only=True)
    skipped_count = serializers.IntegerField(read_only=True)
    remaining_meals = serializers.IntegerField(source='scheduled_count', read_only=True)

    class Meta:
        model = CustomerSubscription
        fields = (
            'public_id',
            'meal_public_id',
            'meal_name_snapshot',
            'meal_period_snapshot',
            'status',
            'started_on',
            'cancel_effective_on',
            'cancelled_at',
            'delivered_count',
            'skipped_count',
            'remaining_meals',
            'customer_note',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class AdminCustomerOrderHistorySerializer(serializers.ModelSerializer):
    meal_public_id = serializers.UUIDField(source='meal.public_id', read_only=True)
    delivered_count = serializers.IntegerField(read_only=True)
    skipped_count = serializers.IntegerField(read_only=True)
    remaining_meals = serializers.IntegerField(source='scheduled_count', read_only=True)

    class Meta:
        model = Order
        fields = (
            'public_id',
            'meal_public_id',
            'meal_name_snapshot',
            'meal_type_snapshot',
            'meal_period_snapshot',
            'total_price_snapshot',
            'per_meal_price_snapshot',
            'order_status',
            'order_start_date',
            'order_end_date',
            'order_month',
            'service_days_count',
            'delivered_count',
            'skipped_count',
            'remaining_meals',
            'customer_note',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class AdminCustomerMealHistorySerializer(serializers.ModelSerializer):
    order_public_id = serializers.SerializerMethodField()
    subscription_public_id = serializers.SerializerMethodField()
    package_name = serializers.SerializerMethodField()

    class Meta:
        model = OrderDelivery
        fields = (
            'public_id',
            'order_public_id',
            'subscription_public_id',
            'package_name',
            'service_date',
            'meal_period',
            'status',
            'skip_source',
            'note',
            'payment_status',
            'charged_amount',
            'marked_at',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_order_public_id(self, obj):
        if obj.order_id:
            return str(obj.order.public_id)
        return None

    def get_subscription_public_id(self, obj):
        if obj.subscription_id:
            return str(obj.subscription.public_id)
        return None

    def get_package_name(self, obj):
        if obj.order_id:
            return obj.order.meal_name_snapshot
        if obj.subscription_id:
            return obj.subscription.meal_name_snapshot
        return None


class AdminCustomerWalletTransactionSerializer(serializers.ModelSerializer):
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
            'external_ref',
            'note',
            'reviewed_at',
            'rejection_reason',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class AdminCustomerActivitySerializer(serializers.Serializer):
    event_type = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    summary = serializers.CharField()
    refs = serializers.DictField()
