## Why

Referral commission currently accrues when a referred customer’s meal is delivered and charged, as long as both parties have active subscriptions. That under-pays the real business rule: a referrer should earn commission for a referred meal **only when both parties are active subscribers and both consume the exact same meal type on the same service date**. Without referrer same-day / same-meal consumption checks, commissions are paid when the referrer’s meal is OFF or for a different meal/date.

## What Changes

- Tighten accrual eligibility so commission is generated only when:
  - referrer and referred both have an active meal subscription, and
  - both have a delivered (consumed) `OrderDelivery` for the **same `service_date`** and **same `meal_period`**.
- **Lock referrer consumption signal to `OrderDelivery.status = delivered` only** (not `payment_status=charged`). Referred side remains **delivered + charged** because commission amount is based on referred payment.
- **Lock skip → success lifecycle to in-place upgrade** of the same `ReferralCommission` row (one delivery = one commission lifecycle); do not create a second success row.
- Record machine-readable `skipped` reasons when the referrer lacks matching meal consumption (and related edge cases).
- Cover ordering races: if the referred meal completes first and the referrer’s matching meal is not yet delivered, do not pay yet; when the referrer later completes the same meal (or reconcile runs), re-evaluate and credit if still eligible.
- Harden reconcile with a mandatory **`--dry-run`** mode before production writes; update eligibility predicate for real runs.
- Review / add `OrderDelivery` indexes needed for referrer same-day same-meal lookup at production scale.
- Extend tests for meal-off, different meal, different date, both-consumed success, dual-trigger / reconcile, and in-place skip upgrade.
- Update backend docs and add/refresh **mobile**, **customer web**, and **admin panel** frontend docs so clients explain the co-consumption rule and new skip reasons.
- Clarify ops policy for already-paid historical `success` commissions (default: no automatic clawback; admin reverse / optional one-off script).

## Capabilities

### New Capabilities

- `referral-commission-eligibility`: Business rules and accrual behavior for dual active-subscription + same-day same-meal co-consumption eligibility, skip reasons, dual-trigger/reconcile behavior, and historical commission handling.
- `referral-eligibility-client-docs`: Documentation and client-facing contract notes for mobile app, customer web, and admin panel (rule copy, status reasons, UX states; API changes only if needed for clarity).

### Modified Capabilities

- (none in `openspec/specs/` — referral commission requirements currently live under the prior change `referral-affiliate-commission-system`; this change introduces the corrected eligibility capability above and will supersede the looser “both active only” accrual rule at implementation time.)

## Impact

- **Backend services:** `referrals/services/commission.py` (`credit_referral_commission_for_delivery`), optional helpers in `referrals/services/eligibility.py`, trigger sites in `orders/services/order_delivery.py` (and possibly referrer-side re-check), `referrals/management/commands/reconcile_referral_commissions.py`.
- **Models / status reasons:** new skip reason(s) such as `REFERRER_MEAL_NOT_CONSUMED` (and keep existing inactive / amount / float reasons).
- **APIs:** likely additive only (`status_reason` values already exposed on customer/admin commission lists); CSV/admin detail may gain clearer reason/detail if product needs it — not a breaking field rename.
- **Clients:** mobile + customer web should display accurate earnings expectations and skip explanations; admin panel should show eligibility skip reasons for support/audit.
- **Ops / finance:** historical over-paid `success` rows are not auto-reversed by this fix; reconcile must use the new rule going forward, support `--dry-run`, and must not blindly re-credit under the old rule.
- **DB performance:** `OrderDelivery` index review for co-consumption lookup path (today: `(service_date, status)`, `(subscription, status)`, unique `(subscription, service_date, meal_period)` — no dedicated customer composite).
- **Docs:** `referrals/docs/backend/referral-affiliate-commission.md` plus new/updated frontend docs for mobile, customer web, and admin.
