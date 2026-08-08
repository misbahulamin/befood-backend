from django.contrib import admin

from admin_wallet.models import AdminWallet, AdminWalletAuditLog, AdminWalletTransaction


@admin.register(AdminWallet)
class AdminWalletAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'public_id',
        'balance',
        'currency',
        'status',
        'total_customer_payments',
        'total_withdrawn',
        'updated_at',
    )
    readonly_fields = (
        'public_id',
        'balance',
        'total_received',
        'total_manual_added',
        'total_withdrawn',
        'total_expenses',
        'total_customer_payments',
        'created_at',
        'updated_at',
    )


@admin.register(AdminWalletTransaction)
class AdminWalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'type',
        'direction',
        'amount',
        'balance_after',
        'status',
        'method',
        'source',
        'created_at',
    )
    list_filter = ('type', 'direction', 'status', 'method')
    search_fields = ('public_id', 'reference', 'note', 'idempotency_key')
    readonly_fields = (
        'public_id',
        'wallet',
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
        'idempotency_key',
        'metadata',
        'order',
        'order_delivery',
        'customer',
        'actor_admin',
        'customer_wallet_transaction',
        'created_at',
        'updated_at',
    )


@admin.register(AdminWalletAuditLog)
class AdminWalletAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'action',
        'amount',
        'previous_balance',
        'new_balance',
        'actor_admin',
        'created_at',
    )
    list_filter = ('action',)
    readonly_fields = (
        'actor_admin',
        'action',
        'amount',
        'previous_balance',
        'new_balance',
        'reason',
        'transaction',
        'metadata',
        'created_at',
    )
