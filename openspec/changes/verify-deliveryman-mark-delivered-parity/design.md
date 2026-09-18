## Context

Production lunch/dinner completion has two entry points:

1. **Auto cron:** `scripts/cron/run_auto_deliver.sh` → `manage.py auto_deliver_meals` → `orders.services.auto_meal_delivery.run_auto_delivery` → `mark_delivery_and_notify(..., marked_by=None)`.
2. **Deliveryman:** `POST .../deliveryman/deliveries/{public_id}/mark/` → zone check → `mark_delivery_and_notify(..., marked_by=rider_user)`.

Both already share the domain completion pipeline inside `orders.services.order_delivery.mark_delivery` (status transition, `charge_delivered_meal`, Onahar, referral commission) and post-commit FCM via `mark_delivery_and_notify`.

**Verified shared (already correct):**

| Concern | Shared path |
|---------|-------------|
| Status / cancelled parent / terminal conflict | `mark_delivery` |
| Wallet debit + idempotency `meal-delivery:{public_id}` | `charge_delivered_meal` |
| Meal-stop after debit | post-charge evaluation |
| Onahar / referral | best-effort after charge |
| Customer FCM on real → delivered | `notify_meal_delivered` |

**Verified divergence (gap):**

| Gate | Auto-delivery | Deliveryman mark today |
|------|---------------|------------------------|
| `status=scheduled` candidates | queryset filter | not required up-front (terminal handled inside mark) |
| `live_delivery_q(service_date)` | queryset filter | only cancelled-parent check inside mark |
| Exclude `meal_service_blocked_low_balance` | queryset `.exclude(...)` | **missing** |
| Zone membership | N/A | `delivery_in_rider_zone` |
| Actor | `marked_by=None`, note = cron | rider user + optional note |

Related sibling change `filter-low-balance-from-deliveryman-board` hides blocked customers from the board. This change closes the **mark-by-public-id** bypass so eligibility matches cron for non-admin actors.

Stakeholders: field deliverymen, kitchen (no cook for blocked), wallet/ops admins (retain override), customers.

## Goals / Non-Goals

**Goals:**

- Make deliveryman mark-delivered eligibility match auto-delivery for meal-stop blocked customers.
- Keep a single completion pipeline (`mark_delivery_and_notify`) — do not fork charge/notify logic.
- Prefer a small shared eligibility helper so cron queryset and rider mark cannot drift again.
- Document admin override as the only intentional exception.
- Add regression tests for parity and the rider rejection path.

**Non-Goals:**

- Changing cron schedule, lock files, or `run_auto_deliver.sh`.
- Changing kitchen today-meal-requirement APIs.
- Removing admin ability to mark blocked customers.
- Changing wallet charge amounts, idempotency keys, or Onahar/referral behavior.
- Implementing board list filtering (owned by `filter-low-balance-from-deliveryman-board`).

## Decisions

### 1. Shared low-balance / cooking-eligibility helper for non-admin mark + cron

- **Choice:** Extract (or reuse from `meal_demand`) a Q/helper for “customer is meal-stop blocked” and a predicate `customer_blocked_for_auto_delivery(delivery)`; use it in `eligible_delivery_queryset` and in deliveryman mark before calling `mark_delivery_and_notify`.
- **Why:** Cron already duplicates the same Q as kitchen (`meal_demand`); rider mark must use the same rule without copy-paste drift.
- **Alternatives considered:**
  - Put the check only in `mark_delivery` for all actors → would break admin override required by `wallet-meal-stop`.
  - Rely only on board filtering → insufficient; riders (or stale clients) can still POST a known `public_id`.

### 2. Reject on deliveryman mark with stable error, do not silently no-op

- **Choice:** When blocked, raise/map to `DeliveryError` (or zone-style error) with code e.g. `MEAL_SERVICE_BLOCKED_LOW_BALANCE`, HTTP `422`, delivery stays `scheduled`, no wallet debit.
- **Why:** Matches wallet failure UX already on this endpoint; clear for mobile.
- **Alternatives considered:** `403` / `409` — less consistent with existing wallet `422` on this view.

### 3. Do not move zone check into `mark_delivery`

- **Choice:** Keep `delivery_in_rider_zone` in the deliveryman view; cron has no zone concept.
- **Why:** Zone auth is actor-specific; domain mark stays reusable for admin + cron.

### 4. Admin override stays outside this gate

- **Choice:** Only deliveryman (and cron candidate selection) apply the low-balance exclude; admin subscription/order mark APIs unchanged.
- **Why:** Spec already requires admin override for ops exceptions (food already given, disputes).

### 5. Verify other mark gates via tests, not a second implementation

- **Choice:** Add an integration-style test that deliveryman successful mark hits the same charge path as a cron-delivered slot (idempotency, no double debit when cron runs after rider). Existing auto-delivery tests already cover rider-then-cron; extend with blocked-customer cases.
- **Why:** Avoid re-implementing wallet rules in the zone app.

## Risks / Trade-offs

- **[Risk] Rider already handed food to a blocked customer** → Mitigation: rare if board + kitchen exclude them; ops use **admin** mark; document in frontend/backend docs.
- **[Risk] Helper extraction causes import cycles** (`delivery_zones` ↔ `orders`)** → Mitigation: keep helper in `orders.services` (meal_demand or auto_meal_delivery); view only calls a thin predicate.
- **[Risk] Sibling board-filter change lands separately** → Mitigation: mark-path gate is independently valuable; board change remains complementary, not a substitute.
- **[Trade-off] Slightly stricter rider API** → Acceptable; aligns with “same business logic as cron.”

## Migration Plan

1. Land helper + deliveryman pre-check + tests.
2. Deploy with board filter change when ready (order flexible).
3. No data migration; flag `meal_service_blocked_low_balance` already exists.
4. Rollback: revert the deliveryman pre-check commit; cron behavior unchanged if helper is backward-compatible.

## Open Questions

- None blocking: error_code name `MEAL_SERVICE_BLOCKED_LOW_BALANCE` is preferred; confirm with frontend copy if needed during apply.
