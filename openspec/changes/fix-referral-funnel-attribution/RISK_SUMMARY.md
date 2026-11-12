# Residual product risk (task 6.3)

## Mobile-only attribution + web invite links

Share / invite URLs resolve on **web**. Backend correctly rejects `referral_code` on web registration. Credited signup still requires the mobile app to re-send the code with `X-Client-Type: mobile` on a brand-new create.

Until the invite landing deep-links into the app and the app persists the code until create, Valid OK will remain much larger than Registrations even when the backend is healthy.

## Metric definition

`total_successful_validations` remains attempt-based for backward compatibility. Use `unique_successful_validation_codes` and `attribution_rate_vs_unique_ok` when judging conversion quality.

## Email finalize fail-closed

Account creation can succeed without a relationship. Ops should monitor `ReferralAttributionEvent` / `attribution_skips_by_reason` rather than assuming every verified email signup was attributed.

## Open product decisions

1. Allow web attribution for invite landings? (out of scope for this change)
2. Surface `IGNORED_EXISTING_CUSTOMER` on login-of-existing envelopes? (optional UX)
