from django.contrib import admin

from inventory.models import (
    InventoryAdjustment,
    InventoryAuditLog,
    InventoryItem,
    InventoryKitchenUsage,
    InventoryPurchase,
    InventoryPurchaseLine,
    InventoryStockMovement,
    InventoryWastage,
)


class InventoryPurchaseLineInline(admin.TabularInline):
    model = InventoryPurchaseLine
    extra = 0


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'default_unit',
        'category',
        'status',
        'quantity_on_hand',
        'average_unit_cost',
        'minimum_stock_level',
    )
    search_fields = ('name', 'category')
    list_filter = ('status', 'default_unit', 'category')
    readonly_fields = ('public_id', 'name_normalized', 'quantity_on_hand', 'average_unit_cost')


@admin.register(InventoryPurchase)
class InventoryPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'status',
        'total_amount',
        'supplier',
        'created_by',
        'confirmed_at',
    )
    list_filter = ('status',)
    search_fields = ('supplier', 'note')
    inlines = [InventoryPurchaseLineInline]
    readonly_fields = ('public_id', 'wallet_transaction', 'reversal_wallet_transaction')


@admin.register(InventoryStockMovement)
class InventoryStockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'item',
        'type',
        'quantity_delta',
        'quantity_after',
        'actor_admin',
        'created_at',
    )
    list_filter = ('type',)
    search_fields = ('item__name', 'note')
    readonly_fields = ('public_id',)


@admin.register(InventoryKitchenUsage)
class InventoryKitchenUsageAdmin(admin.ModelAdmin):
    list_display = ('public_id', 'item', 'quantity_base', 'purpose', 'issued_by', 'created_at')
    search_fields = ('item__name', 'purpose')


@admin.register(InventoryWastage)
class InventoryWastageAdmin(admin.ModelAdmin):
    list_display = ('public_id', 'item', 'quantity_base', 'reason', 'created_at')


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('public_id', 'item', 'quantity_delta_base', 'reason', 'created_at')


@admin.register(InventoryAuditLog)
class InventoryAuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'actor_admin', 'item', 'purchase', 'created_at')
    list_filter = ('action',)
