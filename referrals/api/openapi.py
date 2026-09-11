# OpenAPI helpers for referrals live primarily on view @extend_schema decorators.
#
# ReferralCommissionSerializer.status_reason is documented via serializer
# help_text / docstring. Additive values include REFERRER_MEAL_NOT_CONSUMED
# (retryable skip when referrer has not delivered the same meal/day).
#
# Admin referral settings:
#   GET|PATCH /api/v1/web/referrals/settings/
#   See AdminReferralProgramSettingsView (referral_commission_percent 0–100).
