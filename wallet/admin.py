from django.contrib import admin

from wallet.models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'customer',
        'balance',
        'currency',
        'status',
        'created_at',
        'updated_at',
    )
    list_filter = ('status', 'currency')
    search_fields = (
        'public_id',
        'customer__user__email',
        'customer__user__username',
        'customer__phone',
    )
    readonly_fields = (
        'public_id',
        'balance',
        'created_at',
        'updated_at',
    )
    ordering = ('-created_at',)
    fieldsets = (
        (
            'Identity',
            {'fields': ('public_id', 'customer')},
        ),
        (
            'Balance',
            {
                'fields': ('balance', 'currency', 'status'),
                'description': (
                    'Balance is read-only in admin. Corrections must go through '
                    'the ledger service (future adjustment type), not raw edits.'
                ),
            },
        ),
        (
            'Timestamps',
            {'fields': ('created_at', 'updated_at')},
        ),
    )


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'invoice_number',
        'wallet',
        'type',
        'direction',
        'amount',
        'balance_after',
        'status',
        'method',
        'created_at',
    )
    list_filter = ('type', 'direction', 'status', 'method')
    search_fields = (
        'public_id',
        'invoice_number',
        'external_ref',
        'idempotency_key',
        'note',
        'wallet__public_id',
        'wallet__customer__user__email',
    )
    readonly_fields = (
        'public_id',
        'invoice_number',
        'wallet',
        'type',
        'direction',
        'amount',
        'balance_after',
        'status',
        'method',
        'external_ref',
        'idempotency_key',
        'created_at',
        'updated_at',
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
