from django.contrib import admin

from onahar.models import (
    OnaharAuditLog,
    OnaharContribution,
    OnaharDistribution,
    OnaharDistributionMedia,
    OnaharFundLedgerEntry,
    OnaharMonthlyProgress,
    OnaharPointEvent,
    OnaharPrivacyPreference,
    OnaharSettings,
    OnaharTargetHistory,
)


@admin.register(OnaharSettings)
class OnaharSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'contribution_target',
        'total_contributed_meals',
        'total_distributed_meals',
        'available_meals',
        'updated_at',
    )
    readonly_fields = (
        'total_contributed_meals',
        'total_distributed_meals',
        'available_meals',
        'created_at',
        'updated_at',
    )

    def has_add_permission(self, request):
        return not OnaharSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OnaharTargetHistory)
class OnaharTargetHistoryAdmin(admin.ModelAdmin):
    list_display = ('previous_target', 'new_target', 'changed_by', 'created_at')
    readonly_fields = ('previous_target', 'new_target', 'changed_by', 'created_at')


@admin.register(OnaharMonthlyProgress)
class OnaharMonthlyProgressAdmin(admin.ModelAdmin):
    list_display = (
        'customer',
        'year_month',
        'net_points',
        'target_snapshot',
        'contributions_earned',
        'expired_points',
        'status',
    )
    list_filter = ('status', 'year_month')
    search_fields = ('customer__user__username', 'customer__phone', 'year_month')


@admin.register(OnaharPointEvent)
class OnaharPointEventAdmin(admin.ModelAdmin):
    list_display = ('customer', 'event_type', 'points_delta', 'year_month', 'order_delivery', 'created_at')
    list_filter = ('event_type', 'year_month')


@admin.register(OnaharContribution)
class OnaharContributionAdmin(admin.ModelAdmin):
    list_display = ('public_id', 'customer', 'year_month', 'meals', 'kind', 'created_at')
    list_filter = ('kind', 'year_month')


class OnaharDistributionMediaInline(admin.TabularInline):
    model = OnaharDistributionMedia
    extra = 0


@admin.register(OnaharDistribution)
class OnaharDistributionAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'status',
        'distribution_date',
        'meals_distributed',
        'location',
        'published_at',
    )
    list_filter = ('status',)
    inlines = [OnaharDistributionMediaInline]
    search_fields = ('title', 'location')


@admin.register(OnaharFundLedgerEntry)
class OnaharFundLedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'direction',
        'meals',
        'entry_type',
        'balance_after',
        'created_at',
    )
    list_filter = ('direction', 'entry_type')
    readonly_fields = (
        'public_id',
        'direction',
        'meals',
        'entry_type',
        'balance_after',
        'contribution',
        'distribution',
        'note',
        'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OnaharPrivacyPreference)
class OnaharPrivacyPreferenceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'display_mode', 'updated_at')


@admin.register(OnaharAuditLog)
class OnaharAuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'actor', 'created_at')
    list_filter = ('action',)
    readonly_fields = (
        'action',
        'actor',
        'previous_value',
        'new_value',
        'metadata',
        'created_at',
    )

    def has_add_permission(self, request):
        return False
