# Diagnostics baseline (tasks 1.1–1.3)

Captured during `/opsx:apply` on 2026-10-11 against local/dev DB + source review.
Production chart in the original report showed ~54 validations / ~27 Valid OK / ~5 Registrations / ~2 Subscribers.

## 1.1 Funnel counts (same conceptual window as admin analytics)

Local DB sample (`manage.py shell`, last 30 days):

| Metric | Count |
|--------|------:|
| `ReferralValidationEvent(is_valid=True)` | 2 |
| `ReferralRelationship` | 1 |
| All-time validations | 18 |
| All-time relationships | 3 |

Interpretation: even on a small local set, successful validates can exceed relationships. Admin UI Valid OK is attempt-based (`ReferralValidationEvent`), Registrations are relationship-based — matching the production chart gap.

## 1.2 Attribution skip logging today

`finalize_pending_registration` catches `ReferralError` and logs only:

```text
Referral attribution skipped/failed for customer_id=%s
```

No `error_code`, `referral_code`, or `client_type` in the log. Ops cannot distinguish `REFERRER_INACTIVE` vs `REFERRAL_MOBILE_ONLY` vs self-referral from logs alone. This change adds `ReferralAttributionEvent` + structured log fields.

## 1.3 Create-path contract vs mobile docs

| Path | Docs expect | Backend gate |
|------|-------------|--------------|
| `POST /referrals/validate/` | Optional pre-check | Analytics only; no mobile header required |
| Email register | `referral_code` + `X-Client-Type: mobile` | Stored on pending; attributed at finalize |
| Phone OTP verify | same | Attribute only if `created=True` |
| Google / Facebook | same | Attribute only if `created=True` |
| Web register with code | Must not send | Serializer `422` / `REFERRAL_MOBILE_ONLY` |

Gap vs funnel symptom: validate success does not persist intent server-side. If the client does not re-send `referral_code` on create (or uses web), registration succeeds without `ReferralRelationship`.
