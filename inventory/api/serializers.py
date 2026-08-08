from decimal import Decimal

from rest_framework import serializers

from inventory.models import (
    InventoryAdjustment,
    InventoryAuditLog,
    InventoryItem,
    InventoryKitchenUsage,
    InventoryPurchase,
    InventoryPurchaseLine,
    InventoryStockMovement,
    InventoryUnit,
    InventoryWastage,
)
from inventory.services.items import stock_signals
from inventory.services.ledger import inventory_value
from meals.models import Ingredient


class InventoryItemSerializer(serializers.ModelSerializer):
    out_of_stock = serializers.SerializerMethodField()
    low_stock = serializers.SerializerMethodField()
    stock_value = serializers.SerializerMethodField()
    linked_ingredient_public_id = serializers.UUIDField(
        source='linked_ingredient.public_id',
        read_only=True,
        allow_null=True,
    )
    created_by_email = serializers.EmailField(
        source='created_by.user.email',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = InventoryItem
        fields = [
            'public_id',
            'name',
            'default_unit',
            'category',
            'status',
            'minimum_stock_level',
            'quantity_on_hand',
            'average_unit_cost',
            'stock_value',
            'out_of_stock',
            'low_stock',
            'linked_ingredient_public_id',
            'created_by_email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'public_id',
            'quantity_on_hand',
            'average_unit_cost',
            'stock_value',
            'out_of_stock',
            'low_stock',
            'created_by_email',
            'created_at',
            'updated_at',
        ]

    def get_out_of_stock(self, obj):
        return obj.is_out_of_stock

    def get_low_stock(self, obj):
        return obj.is_low_stock

    def get_stock_value(self, obj):
        return inventory_value(obj)


class InventoryItemWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    default_unit = serializers.ChoiceField(choices=InventoryUnit.choices)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=InventoryItem.Status.choices,
        required=False,
        default=InventoryItem.Status.ACTIVE,
    )
    minimum_stock_level = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        required=False,
        allow_null=True,
    )
    linked_ingredient_public_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_linked_ingredient_public_id(self, value):
        if value is None:
            return None
        try:
            return Ingredient.objects.get(public_id=value)
        except Ingredient.DoesNotExist as exc:
            raise serializers.ValidationError('Ingredient not found.') from exc


class InventoryItemUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    default_unit = serializers.ChoiceField(
        choices=InventoryUnit.choices, required=False
    )
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=InventoryItem.Status.choices, required=False
    )
    minimum_stock_level = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        required=False,
        allow_null=True,
    )
    linked_ingredient_public_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_linked_ingredient_public_id(self, value):
        if value is None:
            return None
        try:
            return Ingredient.objects.get(public_id=value)
        except Ingredient.DoesNotExist as exc:
            raise serializers.ValidationError('Ingredient not found.') from exc


class InventoryPurchaseLineSerializer(serializers.ModelSerializer):
    item_public_id = serializers.UUIDField(source='item.public_id', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = InventoryPurchaseLine
        fields = [
            'item_public_id',
            'item_name',
            'quantity',
            'unit',
            'quantity_base',
            'line_total',
            'unit_cost',
        ]


class InventoryPurchaseLineWriteSerializer(serializers.Serializer):
    item_public_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit = serializers.ChoiceField(choices=InventoryUnit.choices, required=False)
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2)


class InventoryPurchaseSerializer(serializers.ModelSerializer):
    lines = InventoryPurchaseLineSerializer(many=True, read_only=True)
    created_by_email = serializers.EmailField(
        source='created_by.user.email', read_only=True, allow_null=True
    )
    wallet_transaction_public_id = serializers.UUIDField(
        source='wallet_transaction.public_id', read_only=True, allow_null=True
    )
    has_invoice = serializers.SerializerMethodField()
    invoice_url = serializers.SerializerMethodField()

    class Meta:
        model = InventoryPurchase
        fields = [
            'public_id',
            'status',
            'purchase_date',
            'supplier',
            'note',
            'total_amount',
            'currency',
            'has_invoice',
            'invoice_url',
            'created_by_email',
            'wallet_transaction_public_id',
            'confirmed_at',
            'cancelled_at',
            'lines',
            'created_at',
            'updated_at',
        ]

    def get_has_invoice(self, obj):
        return bool(obj.invoice)

    def get_invoice_url(self, obj):
        if not obj.invoice:
            return None
        request = self.context.get('request')
        url = obj.invoice.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class InventoryPurchaseCreateSerializer(serializers.Serializer):
    lines = InventoryPurchaseLineWriteSerializer(many=True)
    supplier = serializers.CharField(required=False, allow_blank=True, max_length=255)
    note = serializers.CharField(required=False, allow_blank=True)
    purchase_date = serializers.DateField(required=False, allow_null=True)
    confirm = serializers.BooleanField(required=False, default=False)
    invoice = serializers.FileField(required=False, allow_null=True)

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError('At least one line is required.')
        return value

    def validate_invoice(self, value):
        if value is None:
            return value
        content_type = getattr(value, 'content_type', '') or ''
        allowed = {'image/jpeg', 'image/png', 'application/pdf', 'image/jpg'}
        name = (getattr(value, 'name', '') or '').lower()
        if content_type not in allowed and not name.endswith(
            ('.jpg', '.jpeg', '.png', '.pdf')
        ):
            raise serializers.ValidationError(
                'Invoice must be JPG, PNG, or PDF.'
            )
        max_bytes = 10 * 1024 * 1024
        if value.size > max_bytes:
            raise serializers.ValidationError('Invoice file must be at most 10MB.')
        return value


class StockIssueSerializer(serializers.Serializer):
    item_public_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit = serializers.ChoiceField(choices=InventoryUnit.choices, required=False)
    purpose = serializers.CharField(required=False, allow_blank=True, max_length=255)
    menu_reference = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    kitchen_batch = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    note = serializers.CharField(required=False, allow_blank=True)


class WastageSerializer(serializers.Serializer):
    item_public_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit = serializers.ChoiceField(choices=InventoryUnit.choices, required=False)
    reason = serializers.CharField(max_length=255)
    note = serializers.CharField(required=False, allow_blank=True)


class AdjustmentSerializer(serializers.Serializer):
    item_public_id = serializers.UUIDField()
    quantity_delta = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit = serializers.ChoiceField(choices=InventoryUnit.choices, required=False)
    reason = serializers.CharField(max_length=255)
    note = serializers.CharField(required=False, allow_blank=True)


class InventoryStockMovementSerializer(serializers.ModelSerializer):
    item_public_id = serializers.UUIDField(source='item.public_id', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    actor_email = serializers.EmailField(
        source='actor_admin.user.email', read_only=True, allow_null=True
    )

    class Meta:
        model = InventoryStockMovement
        fields = [
            'public_id',
            'item_public_id',
            'item_name',
            'type',
            'quantity_delta',
            'quantity_before',
            'quantity_after',
            'unit',
            'actor_email',
            'note',
            'created_at',
        ]


class KitchenUsageSerializer(serializers.ModelSerializer):
    item_public_id = serializers.UUIDField(source='item.public_id', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    issued_by_email = serializers.EmailField(
        source='issued_by.user.email', read_only=True, allow_null=True
    )
    remaining_stock = serializers.DecimalField(
        source='quantity_after', max_digits=14, decimal_places=3, read_only=True
    )

    class Meta:
        model = InventoryKitchenUsage
        fields = [
            'public_id',
            'item_public_id',
            'item_name',
            'quantity',
            'unit',
            'quantity_base',
            'purpose',
            'menu_reference',
            'kitchen_batch',
            'note',
            'issued_by_email',
            'remaining_stock',
            'created_at',
        ]


class WastageReadSerializer(serializers.ModelSerializer):
    item_public_id = serializers.UUIDField(source='item.public_id', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = InventoryWastage
        fields = [
            'public_id',
            'item_public_id',
            'item_name',
            'quantity',
            'unit',
            'quantity_base',
            'reason',
            'note',
            'quantity_after',
            'created_at',
        ]


class AdjustmentReadSerializer(serializers.ModelSerializer):
    item_public_id = serializers.UUIDField(source='item.public_id', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = InventoryAdjustment
        fields = [
            'public_id',
            'item_public_id',
            'item_name',
            'quantity_delta',
            'unit',
            'quantity_delta_base',
            'reason',
            'note',
            'quantity_after',
            'created_at',
        ]


class InventoryDashboardSerializer(serializers.Serializer):
    total_inventory_items = serializers.IntegerField()
    total_stock_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    today_purchases_count = serializers.IntegerField()
    today_purchases_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    month_purchase_cost = serializers.DecimalField(max_digits=14, decimal_places=2)
    low_stock_count = serializers.IntegerField()
    out_of_stock_count = serializers.IntegerField()
    today_kitchen_usage_count = serializers.IntegerField()
    today_kitchen_usage_quantity = serializers.DecimalField(
        max_digits=14, decimal_places=3
    )
    total_wastage_quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    low_stock_items = serializers.ListField(child=serializers.DictField())
    out_of_stock_items = serializers.ListField(child=serializers.DictField())


class InventoryAuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(
        source='actor_admin.user.email', read_only=True, allow_null=True
    )
    item_public_id = serializers.UUIDField(
        source='item.public_id', read_only=True, allow_null=True
    )
    purchase_public_id = serializers.UUIDField(
        source='purchase.public_id', read_only=True, allow_null=True
    )

    class Meta:
        model = InventoryAuditLog
        fields = [
            'id',
            'action',
            'actor_email',
            'item_public_id',
            'purchase_public_id',
            'previous_value',
            'new_value',
            'reference_id',
            'metadata',
            'created_at',
        ]


class ItemDetailSerializer(InventoryItemSerializer):
    history_summary = serializers.SerializerMethodField()

    class Meta(InventoryItemSerializer.Meta):
        fields = InventoryItemSerializer.Meta.fields + ['history_summary']

    def get_history_summary(self, obj):
        from inventory.services.queries import item_history_summary

        return item_history_summary(obj)


# Keep stock_signals import used for typing/docs consistency
_ = (stock_signals, Decimal)
