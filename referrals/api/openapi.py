# OpenAPI helpers for referrals live primarily on view @extend_schema decorators.
#
# ReferralCommissionSerializer.status_reason is documented via serializer
# help_text / docstring. Additive values include REFERRER_MEAL_NOT_CONSUMED
# (retryable skip when referrer has not delivered the same meal/day).
#
# Admin referral settings:
#   GET|PATCH /api/v1/web/referrals/settings/
#   See AdminReferralProgramSettingsView (referral_commission_percent 0–100).
#
# Admin analytics (GET /api/v1/web/referrals/analytics/):
#   Existing: total_validations, total_successful_validations (attempt-based Valid OK),
#   total_successful_registrations (= ReferralRelationship count),
#   total_paid_subscribers_from_referral, conversion_rate (attempt-based).
#   Additive: unique_successful_validation_codes, attribution_rate_vs_unique_ok,
#   attribution_skips_by_reason (map of error_code -> count).
#
# Auth create envelopes (phone / oauth / email verify) may include additive:
#   referral_attributed: bool
#   referral_status_reason: string | null
# when a non-empty referral_code was present on brand-new customer create.
