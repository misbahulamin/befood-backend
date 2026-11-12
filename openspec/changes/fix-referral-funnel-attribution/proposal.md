## Why

Admin conversion funnel shows many Validations / Valid OK but few Registrations / Subscribers, even though invitees do create accounts. Investigation shows validate only logs analytics and never attributes; attribution requires a second create-path call with `referral_code` + `X-Client-Type: mobile` for a brand-new customer. Without clearer observability, pending-intent preservation, and funnel metric definitions, ops cannot tell product drop-off from broken client handoff or silent finalize skips.

## What Changes

- Clarify and harden referral attribution observability so silent email-finalize skips record machine-readable reasons (not only a vague info log).
- Preserve pending email registration referral intent when a later register attempt omits `referral_code` (do not wipe a previously stored code).
- Enrich admin referral analytics so Valid OK is not mistaken for unique users ready to convert; expose attempt vs unique vs attributed metrics.
- Optionally surface `referral_attributed` (+ reason when false) on auth create success envelopes so mobile clients can detect dropped attribution.
- Update frontend/admin docs so validate ≠ attributed registration, and web invite → mobile deep-link handoff is explicit.
- Add regression tests for funnel disconnect, pending intent merge, and finalize skip telemetry.

## Capabilities

### New Capabilities
- `referral-funnel-analytics`: Admin analytics contract that distinguishes validate attempts, successful validates, unique successful validates, attributed registrations (`ReferralRelationship`), and paid subscribers from referral.
- `referral-attribution-observability`: Structured outcomes when attribution is attempted but skipped/failed (email finalize and auth envelopes), without weakening mobile-only / once-per-customer rules.

### Modified Capabilities
- `referral-once-per-customer`: Preserve stored pending referral intent across re-submit of deferred email registration when the later payload omits `referral_code`; keep ignore-on-existing-login behavior.
- `referral-eligibility-client-docs`: Document validate-vs-attribute contract, required headers/fields on create paths, web invite deep-link handoff, and how to read the funnel metrics.

## Impact

- Code: `referrals/services/queries.py`, `referrals/services/attribution.py`, `referrals/api/views.py` (admin analytics), `user_management/services/pending_registration.py`, phone/oauth create paths (optional response fields), serializers/OpenAPI, referral tests and docs under `referrals/docs/` and `user_management/docs/`.
- APIs: additive analytics fields; optional additive auth success fields; no change to mobile-only attribution product rule unless product later decides otherwise.
- Clients: mobile must persist validate/deep-link code until first new-customer create; web must not expect web registration attribution.
- Metrics/UI: admin Conversion Funnel labels and interpretation change; historical Valid OK remains attempt-based.
