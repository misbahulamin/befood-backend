## 1. Eligibility helper and skip reason

- [x] 1.1 Add shared co-consumption eligibility helper (referrer active sub + referred active sub + matching referrer `OrderDelivery` for same `service_date` / `meal_period` with `status=delivered` only — not charged; referred remains delivered+charged) returning pass/fail + machine reason
- [x] 1.2 Introduce `REFERRER_MEAL_NOT_CONSUMED` and implement **in-place** retryable upgrade: same `ReferralCommission` row `skipped` → `success` (never a second success row for the same referred delivery)

## 2. Accrual and dual-trigger wiring

- [x] 2.1 Update `credit_referral_commission_for_delivery` to enforce the helper before Admin Wallet debit / commission credit (including in-place upgrade path)
- [x] 2.2 Keep referred-delivery primary trigger in `order_delivery.mark_delivery` (best-effort, non-blocking)
- [x] 2.3 Add secondary best-effort re-evaluation when a referrer’s matching meal is marked `delivered` (scan referred charged deliveries for same date/period without success commission)
- [x] 2.4 Ensure concurrent dual-trigger paths remain idempotent (no double debit/credit)

## 3. Reconcile, dry-run, and historical policy

- [x] 3.1 Update `reconcile_referral_commissions` to use co-consumption eligibility and in-place skip upgrades
- [x] 3.2 Add `--dry-run` that reports planned creates/upgrades/retries with **zero** wallet/commission money writes; document dry-run-before-prod/cron in command help and backend docs
- [x] 3.3 Document that existing historical `success` rows are not auto-reversed; clawback uses admin reverse / approved one-off only

## 4. OrderDelivery index review

- [x] 4.1 Confirm preferred lookup uses subscription + `service_date` + `meal_period` (existing unique constraint) and assert `status=delivered`
- [x] 4.2 EXPLAIN / review whether additional composite index is needed for the chosen path; add migration only if measured necessary

## 5. Tests

- [x] 5.1 Add unit tests: both same day/period delivered → success
- [x] 5.2 Add unit tests: referrer meal OFF / missing delivery → skip `REFERRER_MEAL_NOT_CONSUMED`
- [x] 5.3 Add unit tests: referrer delivered but not charged still qualifies; different `meal_period` / `service_date` → skip
- [x] 5.4 Add unit/integration tests: referred-first then referrer-later upgrades **same row** skipped → success; repeat accrual stays idempotent
- [x] 5.5 Add reconcile `--dry-run` test (no writes) and confirm existing inactive-referrer / amount / float behaviors still pass

## 6. Documentation (backend + clients)

- [x] 6.1 Update `referrals/docs/backend/referral-affiliate-commission.md` with co-consumption rule, referrer=delivered / referred=charged+delivered, in-place upgrade, dry-run, skip reasons
- [x] 6.2 Update `referrals/docs/frontend/referral-mobile-integration.md` with eligibility UX copy guidance and `status_reason` mapping
- [x] 6.3 Add `referrals/docs/frontend/referral-customer-web.md` for customer web earnings/history expectations
- [x] 6.4 Add `referrals/docs/frontend/referral-admin-panel.md` for admin support/audit (skip reasons, historical SUCCESS, reverse flow, dry-run note)
- [x] 6.5 Note optional OpenAPI/example updates if commission serializers document enum-like `status_reason` values

## 7. Verification

- [x] 7.1 Run referral-focused tests and fix regressions
- [x] 7.2 Smoke-check commission list payloads still expose `status` / `status_reason` for skip outcomes
