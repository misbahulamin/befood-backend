## 1. Diagnostics baseline

- [x] 1.1 Confirm production/staging samples: count `ReferralValidationEvent(is_valid=True)` vs `ReferralRelationship` in the same date window used by the admin funnel chart
- [x] 1.2 Search app logs for `Referral attribution skipped/failed` and note missing `error_code` today
- [x] 1.3 Document current mobile/web create payloads against `referral-mobile-integration.md` (code present? `X-Client-Type: mobile`?)

## 2. Pending referral intent preserve

- [x] 2.1 Update `upsert_pending_registration` to keep prior non-empty referral intent when the new payload omits `referral_code`
- [x] 2.2 Ensure a later non-empty `referral_code` still replaces intent + snapshot + client type + intent timestamp
- [x] 2.3 Add unit/API tests for preserve-on-omit and replace-on-new-code

## 3. Attribution observability

- [x] 3.1 Choose persistence shape for finalize skips (`ReferralAttributionEvent` table or equivalent) with `error_code`, code, client_type, customer_id, stage
- [x] 3.2 Replace bare info log in `finalize_pending_registration` with structured skip recording + keep fail-closed account creation
- [x] 3.3 Add additive `referral_attributed` / `referral_status_reason` on new-customer create success envelopes (phone, oauth, email finalize) when a code was present
- [x] 3.4 Update OpenAPI schemas for the additive auth fields
- [x] 3.5 Add tests: inactive referrer finalize → account ok + structured skip + `referral_attributed=false`

## 4. Funnel analytics enrichment

- [x] 4.1 Add `unique_successful_validation_codes` (and any agreed skip aggregates) in `admin_analytics` without breaking existing fields
- [x] 4.2 Update admin analytics serializer/OpenAPI examples and field descriptions (attempt-based vs attributed)
- [x] 4.3 Add tests: 10 validates of one code → validations=10, unique_codes=1, registrations unchanged until relationship exists

## 5. Client and admin documentation

- [x] 5.1 Update `referrals/docs/frontend/referral-mobile-integration.md` with persist-until-create checklist and envelope fields
- [x] 5.2 Update `referrals/docs/frontend/referral-customer-web.md` with invite → deep-link → no web attribution rule
- [x] 5.3 Add/update admin docs mapping Conversion Funnel labels to API fields and common Valid OK → Registrations drop-off causes
- [x] 5.4 Cross-link identity create-path docs so existing-login ignore behavior stays clear

## 6. Verification

- [x] 6.1 Run referral + pending-registration related pytest modules and fix failures
- [x] 6.2 Smoke admin analytics response shape in Swagger/local against additive fields
- [x] 6.3 Summarize residual product risk (mobile-only + web invite) for stakeholders
