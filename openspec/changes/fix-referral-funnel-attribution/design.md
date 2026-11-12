## Context

Admin Conversion Funnel (`GET /api/v1/web/referrals/analytics/`) maps:

| UI label | API field | Source |
|----------|-----------|--------|
| Validations | `total_validations` | All `ReferralValidationEvent` rows |
| Valid OK | `total_successful_validations` | `is_valid=True` events |
| Registrations | `total_successful_registrations` | Count of `ReferralRelationship` |
| Subscribers | `total_paid_subscribers_from_referral` | Distinct referred customers with ACTIVE subscription |

`POST /referrals/validate/` only calls `record_validation_event` — it never creates `ReferralRelationship`. Attribution runs only inside create paths via `attribute_on_signup()` when:

1. `referral_code` is present on the create request (or stored on pending email registration),
2. `client_type == mobile` (`X-Client-Type: mobile`),
3. the customer is brand-new (`created=True` / first `CustomerProfile`),
4. referrer still has an active meal subscription at attribution time.

Observed symptom (high Valid OK, low Registrations while accounts still get created) matches: clients validate on invite pages, then register without re-sending the code and/or without mobile client type; metrics also count every validate attempt, not unique users. Email finalize additionally swallows `ReferralError` and continues account creation with only an info log.

## Goals / Non-Goals

**Goals:**

- Make attribution drop-offs observable (reason codes in logs/storage and optionally auth responses).
- Stop pending email re-register from wiping a previously stored referral intent when the later payload omits `referral_code`.
- Enrich admin analytics so ops can separate attempt inflation from true attribution conversion.
- Document the validate → persist → create contract for mobile/web/admin.
- Add tests that lock the funnel semantics and pending-intent merge.

**Non-Goals:**

- Enabling web registration attribution (product rule stays mobile-only unless a later change says otherwise).
- Changing commission accrual / co-consumption rules.
- Treating validate as attribution (validate remains analytics-only).
- Guaranteeing Subscribers ≈ Registrations (subscription is a later product step).
- Building a full attribution session store / cookie system in v1 of this fix.

## Decisions

### D1 — Keep validate analytics-only; fix handoff + observability

**Choice:** Do not create `ReferralRelationship` on validate.

**Rationale:** Attribution must bind to a real new customer identity. Validate is AllowAny and can be spammed.

**Alternatives considered:** Server-side short-lived “intent tokens” after validate — deferred; more infra for a problem mostly solvable by client persistence + clearer APIs.

### D2 — Preserve pending referral intent on omit

**Choice:** In `upsert_pending_registration`, if the email already has a pending row with non-empty `referral_code` and the new payload’s code is empty, keep the previous `referral_code`, `referrer_snapshot_id`, `referral_client_type`, and `referral_intent_created_at`. Explicit new non-empty code replaces intent. Explicit clear is out of scope unless product asks later.

**Rationale:** Accidental second submit without code currently blanks intent via `update_or_create` defaults.

**Alternatives considered:** Reject re-register without code — harsher UX; token-based intent — heavier.

### D3 — Structured attribution outcome on email finalize

**Choice:** When finalize catches `ReferralError`, log structured fields (`customer_id`, `referral_code`, `client_type`, `error_code`) and persist a lightweight outcome (prefer extending analytics / a small `ReferralAttributionEvent` or reusing validation-event style table with `outcome`/`stage=finalize`). Keep fail-closed account creation.

**Rationale:** Today ops cannot distinguish REFERRER_INACTIVE vs REFERRAL_MOBILE_ONLY vs other skips from dashboards alone.

**Alternatives considered:** Hard-fail email finalize on referral error — breaks “account still created” auth product rule; only improve logs — insufficient for admin funnel.

### D4 — Additive auth success envelope fields

**Choice:** On phone/oauth/email create success paths where attribution was attempted, add optional `referral_attributed: bool` and `referral_status_reason: string|null` (omitted or null when no code was supplied). Additive only; existing clients ignore unknown fields.

**Rationale:** Mobile can surface “referral not applied” instead of silent success.

**Alternatives considered:** Separate GET after signup — extra round trip; push-only — not enough for support.

### D5 — Enrich funnel analytics (additive fields)

**Choice:** Keep existing fields for backward compatibility. Add at least:

- `unique_successful_validation_codes` — distinct codes with `is_valid=True` in range
- `unique_successful_validation_days` or IP/UA-agnostic distinct count if cheap (codes + date bucket); document that true unique users are still approximate without visitor IDs
- Keep `conversion_rate` as `relationships / successful_validations` but document it as attempt-based; add `attribution_rate_vs_unique_ok` when unique metric exists
- Optional: `attribution_skips_by_reason` from new observability events

**Rationale:** Chart drop Valid OK → Registrations is mostly definitional today.

**Alternatives considered:** Rename existing fields — **BREAKING** for admin UI; avoid.

### D6 — Docs + client checklist over backend policy flip

**Choice:** Explicitly document web invite URL → app deep link must carry `referral_code` into create APIs with `X-Client-Type: mobile`. Do not change mobile-only rule in this change.

**Rationale:** Share links are web (`REFERRAL_LINK_BASE_URL`); web register with code is correctly rejected. The leak is between validate and mobile create.

## Risks / Trade-offs

- [Clients ignore new envelope fields] → Mitigation: docs + mobile checklist; admin still sees skip reasons.
- [Pending intent preserve applies wrong code after user changes mind] → Mitigation: non-empty new code always replaces; document behavior.
- [Analytics unique metrics still overcount users] → Mitigation: label as code/attempt uniqueness, not people; optional future visitor id.
- [Extra write on finalize skip] → Mitigation: single insert/log; no hot path on validate.
- [Product expects web attribution] → Mitigation: call out as open product decision; not silently enabled.

## Migration Plan

1. Ship additive analytics fields + structured skip logging/events (backward compatible).
2. Deploy pending-intent preserve + tests.
3. Deploy optional auth envelope fields; update OpenAPI.
4. Update admin UI labels/docs to “validate attempts” vs “attributed registrations”.
5. Coordinate mobile deep-link persistence release.
6. Rollback: feature is additive; revert pending merge logic independently if needed (previous wipe behavior returns).

## Open Questions

1. Should product eventually allow web attribution for invite landing pages, or keep mobile-only forever?
2. Is a dedicated `ReferralAttributionEvent` table preferred over structured logs + optional Redis/metrics only?
3. Should auth envelopes include referral outcome on login-of-existing (always `false` / `IGNORED_EXISTING_CUSTOMER`) for clearer client UX?
