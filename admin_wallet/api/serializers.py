from decimal import Decimal

from rest_framework import serializers

from admin_wallet.models import AdminWalletAuditLog, AdminWalletTransaction


class AdminWalletSummarySerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    total_received = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_manual_added = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_withdrawn = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_customer_payments = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text='Recognized meal-delivery revenue (charged deliveries), not funding credits.',
    )
    total_customer_funding = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_customer_withdrawals = serializers.DecimalField(max_digits=14, decimal_places=2)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class AdminWalletTransactionSerializer(serializers.ModelSerializer):
    order_public_id = serializers.UUIDField(source='order.public_id', allow_null=True, read_only=True)
    delivery_public_id = serializers.UUIDField(
        source='order_delivery.public_id',
        allow_null=True,
        read_only=True,
    )
    customer_public_id = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    admin_email = serializers.SerializerMethodField()

    class Meta:
        model = AdminWalletTransaction
        fields = (
            'public_id',
            'type',
            'direction',
            'amount',
            'balance_after',
            'status',
            'method',
            'source',
            'reference',
            'reason',
            'note',
            'external_ref',
            'order_public_id',
            'delivery_public_id',
            'customer_public_id',
            'customer_email',
            'admin_email',
            'metadata',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_customer_public_id(self, obj):
        if obj.customer_id and hasattr(obj.customer, 'public_id'):
            return obj.customer.public_id
        return None

    def get_customer_email(self, obj):
        if obj.customer_id and obj.customer.user_id:
            return obj.customer.user.email
        return None

    def get_admin_email(self, obj):
        if obj.actor_admin_id and obj.actor_admin.user_id:
            return obj.actor_admin.user.email
        return None


class AdminWalletDashboardSerializer(serializers.Serializer):
    wallet = AdminWalletSummarySerializer()
    today_income = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text='Completed Admin Wallet cash credits today (includes customer_funding).',
    )
    today_expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    month_revenue = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text='Completed Admin Wallet cash credits this month (includes customer_funding).',
    )
    month_expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_customer_payments = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text='Lifetime meal-delivery revenue from charged deliveries.',
    )
    total_customer_funding = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_customer_withdrawals = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_withdrawn = serializers.DecimalField(max_digits=14, decimal_places=2)
    recent_transactions = AdminWalletTransactionSerializer(many=True)


class ManualDepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    reason = serializers.CharField(max_length=255)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class WithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    reason = serializers.CharField(max_length=255)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class ExpenseSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    type = serializers.ChoiceField(choices=sorted(AdminWalletTransaction.EXPENSE_TYPES))
    reason = serializers.CharField(max_length=255)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    reference = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    order_public_id = serializers.UUIDField(required=False, allow_null=True)
    customer_public_id = serializers.UUIDField(required=False, allow_null=True)


class AuditLogSerializer(serializers.ModelSerializer):
    admin_email = serializers.SerializerMethodField()
    transaction_public_id = serializers.UUIDField(
        source='transaction.public_id',
        allow_null=True,
        read_only=True,
    )

    class Meta:
        model = AdminWalletAuditLog
        fields = (
            'id',
            'action',
            'amount',
            'previous_balance',
            'new_balance',
            'reason',
            'admin_email',
            'transaction_public_id',
            'metadata',
            'created_at',
        )
        read_only_fields = fields

    def get_admin_email(self, obj):
        if obj.actor_admin_id and obj.actor_admin.user_id:
            return obj.actor_admin.user.email
        return None
