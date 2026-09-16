## Context

BeFood already has:

- **Users:** Django `User` + `CustomerProfile`; registration via email pending finalize, phone OTP, and social OAuth (`user_management`).
- **Subscriptions:** `CustomerSubscription` (`active` | `cancelled`) — no separate “meal subscription expired” state; “meal off” is per-slot `OrderDelivery.skipped`.
- **Meal consumption:** `OrderDelivery` marked `delivered` via `mark_delivery()` (admin + auto-delivery cron); wallet charge in `charge_delivered_meal()` using slot `final_meal_price_snapshot` → `charged_amount`.
- **Customer wallet:** Single `Wallet.balance` today; funding via pending approve/reject; withdraw reserves from total balance.
- **Admin wallet:** Platform float with typed ledger (`admin_wallet`); meal revenue and custody already wired.
- **Precedent:** Onahar credits after successful delivery charge inside `mark_delivery` (best-effort, idempotent, non-blocking).

There is **no** referral/affiliate code today. Commission requires attribution at signup, dual-bucket wallet accounting, auditable status/reversal support, and growth + finance reporting.

Stakeholders: mobile growth, finance, operations, existing meal/wallet clients.

## Goals / Non-Goals

**Goals:**

- Production-ready referral program: unique `BEF`+8 codes, mobile-only attribution, immutable one-referrer rule.
- Commission on each **charged delivered meal** when both parties have an active `CustomerSubscription`.
- Explicit commission status machine + reversal/manual-adjustment model support.
- Atomic Admin Wallet debit + referrer commission credit with full audit ledger and CSV export.
- Dual wallet buckets with migration validation and ongoing consistency verification.
- Indexed aggregates (no stats table); admin finance + conversion analytics.
- Service-layer isolation in `referrals`; thin hooks from auth and delivery.

**Non-Goals:**

- Multi-level / MLM trees.
- Cash payout of commission.
- Changing meal pricing, subscription pricing, or Onahar rules.
- Website referral registration.
- Full click/ad-network tracking platform (v1 uses validate + registration events; optional share counters only).
- Enforcing device-id / same-phone fraud blocks in v1 (schema/docs reserved for later).
- Replacing `promotions` coupon stub.

## Decisions

### 1. New Django app `referrals`

Dedicated app with models, services, customer + web APIs, docs, tests. Auth/wallet remain thin callers.

### 2. Model design

| Model | Role |
|-------|------|
| `ReferralProfile` | 1:1 customer; unique permanent `code`; optional `share_count`, `last_shared_at` |
| `ReferralRelationship` | Immutable referrer → referred (unique `referred`); code used; `source_client`; `attributed_at` |
| `ReferralCommission` | Per delivery (or manual) audit row with status machine, amounts, wallet refs, optional `reversal_of` / reversed-by linkage |
| Settings | Env/`REFERRAL_*` (optional DB override later) |

**No `ReferralStatistics` table in v1** — aggregate via indexed queries.

### 3. Referral code format

- **`BEF` + exactly 8** uppercase alphanumeric characters (e.g. `BEF8A92KX`).
- Collision retry + DB unique constraint.
- Created at customer creation + backfill command.

### 4. Active meal eligibility mapping

| Product phrase | Implementation |
|----------------|----------------|
| Active meal subscription | `get_active_subscription()` → `status=active` |
| Code usable | Referrer has active subscription (meal-off does **not** disable code) |
| Meal consume | `OrderDelivery` → `delivered` + charged (`charged_amount`) |
| Both active | Re-checked at accrual time |

### 5. Attribution + pending reservation

**Hooks:** finalize pending (mobile), phone OTP new user, social `created_user=True`.

**Pending email path stores:**

- `referral_code`
- `referrer_snapshot_id` (CustomerProfile PK/public id of referrer resolved at submit time, if code valid then)
- `referral_intent_created_at` (or reuse pending `created_at`)

**Finalize rule:** Always re-validate eligibility (active subscription) at finalize. Snapshot is for audit/debug only — **not** a guarantee of attribution if referrer became inactive. Fail with `"Your referrer does not have an active meal subscription."` when inactive at finalize.

Web + `referral_code` → **422**.

### 6. Commission status machine

`ReferralCommission.status`:

| Status | Meaning |
|--------|---------|
| `pending` | Accrual started / reserved before money movement completes |
| `success` | Admin debit + user commission credit completed |
| `failed` | Money movement failed (e.g. admin float shortfall); eligible for reconcile retry |
| `skipped` | Business rule skip (inactive subscription, amount &lt; 0.01, no relationship) |
| `reversed` | Previously successful commission was reversed |

Store `status_reason` (machine-readable code + human detail).

**v1 accrual behavior:** create row → move money → `success`; float shortfall → `failed`; eligibility miss → `skipped` (optionally without money attempts).

### 7. Commission reversal (model + service seam in v1)

**Why:** Delivery may later be cancelled/corrected; commission must not silently remain.

**Design:**

- `ReferralCommission` links: `reversal_of` (FK nullable self) or `reversed_commission_id`.
- Wallet types: `referral_commission` (credit) and `referral_commission_reversal` (debit from commission bucket).
- Admin Wallet: matching credit/reversal of the expense type.
- Service: `reverse_referral_commission(commission, *, reason, actor)` — only from `success` → `reversed`; idempotent; cannot reverse twice.
- **Hook wiring** to delivery un-mark/cancel may be partial in v1, but **model + service + admin-triggerable reverse MUST ship** so finance is not blocked.

Manual adjustment: admin API posts signed amount (+/−) with required `reason`, creates commission row `type=manual` (or separate flag) and wallet movement; full audit (actor, timestamp, reason).

### 8. Commission accrual hook

`mark_delivery` after successful `charge_delivered_meal`, parallel to Onahar:

```text
charge_delivered_meal → Onahar credit → credit_referral_commission_for_delivery
```

Best-effort for delivery path (never block meal); money fail-closed (no user credit without admin debit). Idempotency: unique success-path per delivery + `idempotency_key=referral-commission:{delivery.public_id}`.

Formula: half-up 2dp of `charged_amount * percent / 100`; skip &lt; 0.01 as `skipped`.

### 9. Wallet dual-bucket + consistency

Fields: `recharge_balance`, `commission_balance`, denormalized `balance = sum`.

**Migration (production-safe):**

1. Add columns nullable/default 0.
2. Data migration: `recharge_balance = balance`, `commission_balance = 0`.
3. Validate **every** wallet: `balance == recharge_balance + commission_balance`.
4. Ship management command `verify_wallet_balance_consistency` (exit non-zero on drift; used in deploy/CI ops).

**Ledger audit fields (HIGH):** every completed wallet txn MUST persist enough to verify:

- `balance_after` (total)
- `recharge_balance_after`
- `commission_balance_after`

Invariant: `balance_after == recharge_balance_after + commission_balance_after`.

**Debit order:** meal payment burns **commission first**, then recharge (reduce non-withdrawable liability). **Keep.**

Withdraw: only `recharge_balance`.

### 10. Indexes (explicit)

`ReferralCommission`:

- `(referrer_id, created_at)`
- `(referred_id)`
- `(order_delivery_id)` unique where applicable
- `(status)`
- optional `(status, created_at)` for reconcile queues

`ReferralRelationship`:

- `(referrer_id)`
- unique `(referred_id)`
- `(attributed_at)` / `created_at`

### 11. APIs

**Customer:** `/referrals/me/`, referred-users, commissions, `POST /referrals/validate/` with **IP-based throttle** (and auth throttle if authenticated). Device throttle: future.

**Admin:** analytics (finance + conversion), relationships, commissions, customer detail, **CSV export** of commission report, **manual adjustment**, commission reverse action.

**Conversion metrics (v1):**

| Metric | Source |
|--------|--------|
| Total referral validations | Count validate API successes (and optionally failures) via lightweight `ReferralValidationEvent` or structured metrics log table |
| Total successful registrations | Count `ReferralRelationship` |
| Total paid subscribers from referral | Referred users who later have/had active subscription |
| Conversion rate | registrations / validations (define zero-safe) |
| Optional share_count | Increment via me/share endpoint or client report — medium priority |

“Clicks” in v1 ≈ validation attempts (document clearly); full redirect-click tracker deferred.

### 12. Fraud prevention

**v1 enforced:** one referrer, immutable, self-block, subscription checks, charged-delivery only, idempotency, IP throttle on validate.

**Reserved for later (document in models/metadata, do not block ship):** same phone / device id / email-domain heuristics as optional flags.

### 13. Service layer

```text
referrals/services/
  codes.py
  eligibility.py
  attribution.py
  commission.py          # credit, reverse, manual_adjust
  queries.py             # stats, conversion, admin lists
  reconcile.py
  events.py              # validation event recording (lightweight)

wallet/.../ledger.py     # buckets + after snapshots
wallet/management/.../verify_wallet_balance_consistency.py
```

### 14. Observability

Structured logs; `reconcile_referral_commissions`; `verify_wallet_balance_consistency`.

## Risks / Trade-offs

- [Migration drift] → Post-migrate validation + `verify_wallet_balance_consistency`.
- [Delivery cancel without reverse hook] → Ship reverse service + admin action in v1; wire auto-hook as follow-up if delivery cancel API exists.
- [Validate ≠ true link click] → Document conversion denominator; optional share counters MEDIUM.
- [Header spoof mobile] → Accept v1; attestation later.
- [Commission-first burn] → Intentional liability reduction.
- [Pending delay / referrer goes inactive] → Finalize re-check; snapshot is audit-only.

## Migration Plan

1. Wallet columns + data backfill + invariant check + verify command.
2. Ledger after-balance bucket columns; deploy wallet code paths.
3. Referral models/indexes/code backfill.
4. Attribution + pending snapshot fields.
5. Accrual + reverse/manual services; mark_delivery hook.
6. Customer + admin APIs including CSV + analytics.
7. Enable `REFERRAL_ENABLED` staging → production.

**Rollback:** Disable flag; keep buckets; do not drop columns casually.

## Open Questions

1. Exact deep-link URL format for `REFERRAL_LINK_BASE_URL`.
2. Auto-call `reverse_referral_commission` on which delivery lifecycle events? (admin un-deliver / refund — confirm with ops).
3. Whether validation events are DB rows vs metrics-only store (**default: small append-only event table for admin conversion accuracy**).
4. Manual adjustment max absolute amount / dual-control approval (**default: single verified admin + required reason in v1**).
