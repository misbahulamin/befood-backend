## Context

Referral commission accrual already runs from `orders/services/order_delivery.py` → `referrals/services/commission.py::credit_referral_commission_for_delivery` after a referred customer’s meal is marked `delivered` and charged. Today the gate is “both parties have an active `CustomerSubscription`.” Product now requires **co-consumption**: referrer and referred must both consume the **same `service_date` + `meal_period`** while both remain active subscribers.

Prior OpenSpec (`referral-affiliate-commission-system`) documented the looser rule. Mobile/admin already expose `status` / `status_reason` on commission lists, but copy and docs still describe “earn on referred meal consumption” without the referrer meal match.

Stakeholders: finance (over-accrual risk), customer support (why no commission), mobile/customer web (earnings expectations), admin panel (audit / reverse).

## Goals / Non-Goals

**Goals:**

- Enforce: *A referrer earns commission from a referred customer’s meal only when both are active subscribers and both consume the exact same meal on the same day.*
- Keep delivery / meal charge path non-blocking (referral failures stay best-effort).
- Handle meal ordering races fairly (referred-first vs referrer-first) without double-pay.
- Update reconcile to use the new eligibility predicate, with safe **`--dry-run`** before production writes.
- Document behavior for backend + mobile + customer web + admin panel.
- Define a clear historical-commission policy (no silent auto-clawback by default).
- Lock production-ready decisions on referrer delivered-vs-charged, skip→success lifecycle, and index review.

**Non-Goals:**

- Changing commission rate, wallet bucket semantics, or Admin Wallet float handling.
- Changing signup attribution / referral code eligibility (still “referrer active subscription”).
- Automatically reversing all historical `success` commissions paid under the old rule.
- Building new commission analytics dashboards.
- Changing meal-off cutoff or delivery marking UX beyond documentation of eligibility impact.
- Requiring referrer `payment_status=charged` for eligibility (explicitly rejected).

## Decisions

### D1 — Canonical eligibility predicate (shared helper)

**Decision:** Add a pure eligibility helper (prefer `referrals/services/eligibility.py` or a dedicated function used by `commission.py`) that, given a referred `OrderDelivery` (or equivalent date/period/customer), returns pass/fail + machine reason:

1. Feature enabled / referred delivery `delivered` + charged / relationship exists (existing referred money path)
2. Referrer active subscription → else `REFERRER_INACTIVE`
3. Referred active subscription → else `REFERRED_INACTIVE`
4. Referrer has matching `OrderDelivery` for same `service_date` + same `meal_period` with status `delivered` → else `REFERRER_MEAL_NOT_CONSUMED`
5. Amount / float checks unchanged

**Matching keys:** `service_date` and `meal_period` from the **referred** delivery.

**Locked — referrer consumption signal (Option A):**

| Party | Required for eligibility |
|-------|--------------------------|
| Referred | `status=delivered` **and** charged (commission is % of referred payment) |
| Referrer | `status=delivered` **only** — do **not** require `payment_status=charged` |

Rationale: eligibility means both parties **consumed** the meal, not that both paid. Complimentary / special-case referrer meals can be `delivered` without a normal charge; those still count as consumption. Referred side stays charged because earnings are based on customer payment.

**Alternatives considered:** Require referrer `charged` (Option B) — rejected; conflates payment with consumption and under-pays fair complimentary cases. Inline checks only in `commission.py` — rejected for DRY/testability.

### D2 — Dual trigger to avoid unfair referred-first skips

**Decision:** Keep primary trigger on **referred** delivery complete. Add a **secondary** best-effort pass when a customer (as referrer) completes their own delivery (`status=delivered`):

1. On referred delivery → evaluate; if referrer meal not yet delivered → `skipped` / `REFERRER_MEAL_NOT_CONSUMED` (retryable — D3).
2. On referrer delivery → for each active referred relationship, find referred deliveries for the same `service_date` + `meal_period` that are delivered+charged and lack a non-manual `success` commission → call the same accrual function (may upgrade prior skip in place).

Idempotency (existing uniqueness / money-movement guards) MUST prevent double credit.

**Alternatives considered:**

- Referred-only check → permanently loses commission when referrer delivers later same day. Rejected as unfair.
- Always leave no row and only rely on nightly reconcile. Rejected as opaque for support until cron runs.

### D3 — Skip → success lifecycle (locked: in-place upgrade)

**Decision:** Persist a `skipped` row with `status_reason=REFERRER_MEAL_NOT_CONSUMED` when the referred meal accrues first and referrer has no matching delivered meal.

When eligibility later becomes true (referrer delivers matching meal, or reconcile):

- **MUST upgrade the existing row in place:** `skipped` → `success` (same `ReferralCommission` PK / lifecycle for that referred delivery).
- **MUST NOT** create a second success row for the same referred delivery.
- Perform Admin Wallet debit + referrer commission credit only when transitioning into `success`, inside the same transactional rules as a fresh accrual.
- One referred delivery = one commission lifecycle (audit-friendly).

**Alternatives considered:** Create a new success row (Option 2) — rejected; breaks “one delivery = one lifecycle” and complicates uniqueness/audit. Silent `None` until both consumed — harder for admin visibility. Permanent skip — unfair for ordering race.

### D4 — Historical over-payments

**Decision:** Deploying the stricter rule applies **forward** (new accruals + reconcile going forward). Existing `success` commissions created under the old rule are **not** auto-reversed. Ops may use existing admin reverse API / a documented optional one-off script if finance requires clawback. Document this explicitly in backend + admin docs.

### D5 — Reconcile command (locked: `--dry-run` required)

**Decision:** Update `reconcile_referral_commissions` so backfill and failed retries use the same eligibility helper (including co-consumption and in-place upgrade of retryable `REFERRER_MEAL_NOT_CONSUMED` skips).

**Safety:**

- Add a **`--dry-run`** flag that reports what would be created / upgraded / retried **without** writing wallet or commission money movements.
- Production / cron MUST document: run `--dry-run` first (or gate first prod use behind dry-run review); blind reconcile on the money path is risky.
- Real runs must not re-credit under the old looser rule.

### D6 — Client / documentation surface (mobile, customer web, admin)

**Decision:** Prefer **additive API** (new `status_reason` value). Existing list endpoints already return `status_reason`. Documentation plan:

| Client | Doc target | Content |
|--------|------------|---------|
| Mobile | Update `referrals/docs/frontend/referral-mobile-integration.md` (+ short “eligibility” section) | Rule copy for earnings UI; map `REFERRER_MEAL_NOT_CONSUMED` / inactive reasons to user-facing strings; clarify commission is not guaranteed on every referred meal |
| Customer web | New or extended frontend doc under `referrals/docs/frontend/` (e.g. `referral-customer-web.md`) | Same rule; commission history empty/skip states |
| Admin panel | New `referrals/docs/frontend/referral-admin-panel.md` | Support playbook: why skipped; how to reverse; that historical SUCCESS may predate the rule; dry-run reconcile note for ops |
| Backend | Update `referrals/docs/backend/referral-affiliate-commission.md` | Eligibility flow; referrer=delivered / referred=charged+delivered; in-place skip upgrade; dry-run |

**Frontend code changes (outside this backend repo):** plan only—show eligibility helper text on referral/earnings screens; display `status_reason` with localized copy; admin commission table filter/tooltip for new reason. No mandatory new endpoints unless product later wants a “why not eligible?” preview API (out of scope unless requested).

### D7 — Tests

**Decision:** Extend `referrals/tests/test_referral_core.py` (and mark-delivery integration if practical) for:

- Both same day/period delivered → success (referrer need not be charged)
- Referrer meal OFF / no delivery → skip `REFERRER_MEAL_NOT_CONSUMED`
- Referrer delivered but uncharged / complimentary still counts → success when other gates pass
- Different meal_period → skip
- Different service_date → skip
- Referred first then referrer later → same row upgrades skipped → success
- Inactive referrer / referred unchanged
- Idempotency still holds
- Reconcile `--dry-run` makes no writes

### D8 — OrderDelivery index review (locked as implement task)

**Decision:** Before/with production dual-trigger + reconcile volume, review indexes for the co-consumption lookup.

**Current state (audit):**

- Indexes: `(service_date, status)`, `(order, status)`, `(subscription, status)`
- Unique: `(subscription, service_date, meal_period)` when subscription set
- No direct `customer` column on `OrderDelivery` (customer resolved via subscription/order)

**Preferred query path:** resolve referrer’s subscription(s) → lookup slot by `subscription` + `service_date` + `meal_period` (unique constraint already strong) → assert `status=delivered`.

**If** implementation queries by broader customer/date/period/status joins that EXPLAIN poorly, add a supporting composite index (e.g. `(service_date, meal_period, status)` and/or tighten subscription-path filters). Do not add a speculative unused index without measuring the chosen query path.

## Risks / Trade-offs

- **[Risk] Historical SUCCESS over-accruals remain on books** → Mitigation: document policy; optional finance-led reverse script; do not auto-clawback.
- **[Risk] Dual trigger increases call volume on every delivery** → Mitigation: scoped query via subscription + date/period; best-effort try/except; index review (D8).
- **[Risk] In-place skip→success races with concurrent delivery marks** → Mitigation: row locks / `select_for_update` on commission + delivery; never two money movements.
- **[Risk] Blind reconcile writes after eligibility change** → Mitigation: mandatory `--dry-run`; ops docs; no cron until dry-run reviewed.
- **[Risk] Clients still show outdated “earn when friend eats” copy** → Mitigation: ship docs + reason mapping; coordinate mobile/web/admin release notes with backend deploy.
- **[Risk] Ambiguity if referrer has multiple deliveries same period** → Mitigation: any matching `delivered` delivery for that customer/date/period counts once; accrual still keyed off referred delivery id.
- **[Trade-off] Stricter rule reduces commission volume** → Accepted; matches product intent and reduces unfair payouts.
- **[Trade-off] Referrer uncharged-but-delivered can unlock commission** → Accepted; consumption ≠ payment for referrer.

## Migration Plan

1. Land eligibility helper + commission gate + dual trigger + in-place skip upgrade + tests.
2. Add reconcile `--dry-run`; run dry-run in staging/prod snapshot before enabling write reconcile/cron.
3. Complete OrderDelivery index review; migrate only if chosen query needs it.
4. Deploy backend (schema migrate only if index added; `status_reason` remains free-form CharField).
5. Publish backend + three client docs; share status_reason mapping with app teams.
6. Finance review sample of recent commissions if clawback is desired (manual).
7. **Rollback:** revert to previous accrual function (would resume looser rule); do not delete skip rows.

## Open Questions

- Should finance require a one-off clawback of pre-fix SUCCESS commissions that would fail the new rule? Default: **no** (unchanged).
- Exact user-facing copy for `REFERRER_MEAL_NOT_CONSUMED` in BN/EN for mobile and web (product / localization to confirm).

~~Must referrer delivery be `payment_status=charged`, or is `delivered` enough?~~ → **LOCKED:** referrer `delivered` only; referred remains delivered+charged.
