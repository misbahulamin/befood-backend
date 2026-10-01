## Context

BeFood is production-live. Subscribe today:

1. Customer posts `POST /api/v1/subscriptions/` with `{ plan_public_id, customer_note? }`.
2. `subscribe_customer` checks plan + single active subscription + wallet minimum (no debit).
3. Creates `CustomerSubscription` with `meal_period_snapshot = meal.meal_period` (package period).
4. Same transaction: `ensure_subscription_deliveries` creates lunch/dinner rows using `periods_for_meal_period(snapshot)`.
5. Meal price is charged later on mark-delivered; monthly delivery fee is a **separate manual admin debit** via `wallet.services.delivery_fee.charge_delivery_fee`.

Web (`SubscribeConfirmModal`) and mobile (`SubscribeConfirmPage` + Cubit) already have a confirmation step (wallet/address gates) but do **not** collect meal preference or quantity; they only send `plan_public_id`.

Working-tree WIP already sketches preference/quantity/quote helpers in subscription services/serializers, but the canonical fee module and migration sources are incomplete—this design is the production-safe completion plan. No silent behavior change for existing subscribers.

## Goals / Non-Goals

**Goals**

- Customer selects Lunch / Dinner / Both before confirm; preference persists and drives all future slot generation.
- Canonical quantity on the subscription; fee tiers for `both` use that quantity.
- Single backend fee calculator; clients display returned amounts only.
- Backward-compatible subscribe for old clients (omit preference → package period).
- Additive migration; no rewrite of historical deliveries.

**Non-Goals**

- Auto-debit delivery fee at subscribe (preserve manual admin charging unless product later mandates otherwise).
- Changing per-meal wallet payment, meal ON/OFF deadlines, or cancel cutoff rules.
- Admin UI to edit preference after subscribe (display only in this change).
- Separate lunch vs dinner quantities (one subscription `quantity` only).
- Proration / refund redesign for delivery fees.

## Decisions

### D1 — Prefer reusing `meal_period_snapshot` over a new enum column

**Decision:** Store customer meal preference in existing `CustomerSubscription.meal_period_snapshot` (`lunch` | `dinner` | `both`).

**Why:** Delivery generation already calls `periods_for_meal_period(subscription.meal_period_snapshot)`. Package period stays on `MealCategory.meal_period` as the upper bound. Avoids dual sources of truth.

**Validation:** Selected periods ⊆ package periods. Lunch-only package cannot accept `dinner` or `both`.

### D2 — Add `quantity` as PositiveIntegerField(default=1)

**Decision:** Additive field on `CustomerSubscription`; min 1; canonical for fee tiers and API display.

**Why:** No existing person-count on subscription today; delivery `meal_quantity` (if any) is not the subscription fee source. Clients must not invent quantity.

### D3 — Fee tiers and boundary at quantity `3`

Product copy overlaps `1–3` and `3–5`. **Recommendation (pending product confirm):** non-overlapping tiers:

| Preference | Quantity | Monthly fee (BDT) | `fee_rule_code` |
|------------|----------|-------------------|-----------------|
| lunch | any | 200 | `single_period` |
| dinner | any | 200 | `single_period` |
| both | 1–3 | 400 | `both_q_1_3` |
| both | 4–5 | 350 | `both_q_4_5` |
| both | 6+ | 300 | `both_q_6_plus` |

If product insists `3` belongs to the middle tier, invert middle to `3–5` and top of first to `1–2`—but do not ship ambiguous overlapping ranges.

### D4 — Canonical calculator module

**Decision:** `wallet/services/subscription_delivery_fee.py` with:

- `calculate_subscription_delivery_fee(meal_preference, quantity) -> { amount, fee_rule_code, ... }`
- `normalize_quantity`, `format_fee_summary`

Orders layer calls this for subscribe/quote/serializers; admin customer 360 reuses the same function. No fee amounts in web/mobile.

### D5 — Quote endpoint

**Decision:** `POST /api/v1/subscriptions/quote/` (same ViewSet) returns normalized preference, quantity, `monthly_delivery_fee`, `fee_rule_code`. Prefer this over hardcoding fees client-side. Plans list alone is insufficient because fee depends on client selection.

### D6 — Old client compatibility

**Decision:** `meal_preference` optional. Missing/null → `allow_fallback=True` → use package `meal.meal_period` (historical behavior). After coordinated web+mobile release, optionally require preference for new clients via header/feature flag; keep fallback until store lag clears.

`quantity` defaults to `1` when omitted.

### D7 — Delivery fee charging semantics (preserve)

**Decision:** Subscribe still does **not** debit delivery fee. Calculator is for quote/display and admin suggested amount. Existing `charge_delivery_fee` remains the only debit path. Mid-month proration, renewal auto-charge, and cancel refund stay out of scope (current system has no auto monthly fee cron).

### D8 — Atomicity

**Decision:** Keep `subscribe_customer` in `@transaction.atomic`: create subscription + `ensure_subscription_deliveries` together. No wallet fee debit in that transaction (none today).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Existing subs become lunch/dinner-only | Do not backfill/overwrite `meal_period_snapshot`; only new writes use client preference |
| Old mobile breaks if preference required | Keep optional + package fallback during compatibility window |
| Fee charged twice | Do not call `charge_delivery_fee` from subscribe |
| Schedule path misses preference | All generation uses snapshot via `periods_for_meal_period`; audit cron/publish callers |
| Quantity `3` ambiguity | Explicit non-overlapping tiers in calculator + product confirmation in open questions |
| Incomplete WIP imports crash | Ship fee module + migration before/with API deploy |
| Frontend/backend fee drift | Clients use quote/subscribe response only |

## Migration Plan

1. Additive migration: `CustomerSubscription.quantity` default `1`, `NOT NULL` with server default (safe for existing rows; SQLite/Postgres).
2. No change to `meal_period_snapshot` values for existing rows.
3. No delivery table rewrite.
4. Deploy backend first (compat fallback), then web, then mobile store release.
5. Rollback: reverse quantity migration if needed; preference logic is code-level—reverting code restores package-only snapshot writes; existing new lunch/dinner subs keep their snapshots (correct).

## Open Questions

1. Confirm non-overlapping both tiers: `1–3 / 4–5 / 6+` vs `1–2 / 3–5 / 6+`.
2. Should admin delivery-fee deduct UI auto-fill the calculated amount?
3. After mobile store saturation, when to make `meal_preference` required (drop fallback)?
4. Is quantity editable post-subscribe in a later change? (Out of scope now.)
