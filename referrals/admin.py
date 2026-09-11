from django.contrib import admin

from referrals.models import (
    ReferralCommission,
    ReferralProfile,
    ReferralProgramSettings,
    ReferralRelationship,
    ReferralValidationEvent,
)


@admin.register(ReferralProgramSettings)
class ReferralProgramSettingsAdmin(admin.ModelAdmin):
    list_display = ('commission_percent', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not ReferralProgramSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReferralProfile)
class ReferralProfileAdmin(admin.ModelAdmin):
    list_display = ('code', 'customer', 'share_count', 'created_at')
    search_fields = ('code', 'customer__user__email', 'customer__phone')
    readonly_fields = ('public_id',)


@admin.register(ReferralRelationship)
class ReferralRelationshipAdmin(admin.ModelAdmin):
    list_display = (
        'referrer',
        'referred',
        'referral_code_used',
        'source_client',
        'attributed_at',
    )
    search_fields = ('referral_code_used', 'referrer__user__email', 'referred__user__email')
    readonly_fields = ('public_id',)


@admin.register(ReferralCommission)
class ReferralCommissionAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'status',
        'referrer',
        'referred',
        'commission_amount',
        'is_manual',
        'created_at',
    )
    list_filter = ('status', 'is_manual')
    search_fields = ('public_id', 'referrer__user__email', 'referred__user__email')
    readonly_fields = ('public_id',)


@admin.register(ReferralValidationEvent)
class ReferralValidationEventAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_valid', 'reason', 'client_ip', 'created_at')
    list_filter = ('is_valid',)
    search_fields = ('code',)
