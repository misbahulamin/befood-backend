## Context

BeFood already computes a **final per-meal price** in meal-cycle costing (ingredient product cost + monthly per-meal operational cost + plan profit percent → `per_meal_rate`), publishes it onto `MealCategory.total_price` / per-meal display, and freezes it on package orders as `Order.per_meal_price_snapshot` and `Order.total_price_snapshot`.

Delivery lifecycle lives on `OrderDelivery` (`scheduled` → `delivered` | `skipped` | `missed`). Customer meal-off and admin mark both use `orders.services.order_delivery.mark_delivery` / meal-off services. Wallet already has append-only ledger helpers (`debit_wallet` / `credit_wallet`) with `type=payment` reserved and idempotency keys, but **order create only checks minimum balance** and never debits.

Stakeholders: kitchen/ops and deliverymen who mark deliveries; customers who see wallet history; admins who manage pricing and disputes.

## Goals / Non-Goals

**Goals:**

- Debit wallet by `Order.per_meal_price_snapshot` exactly once when a delivery becomes `delivered`.
- Skip charge for `scheduled`, `skipped` (meal-off or admin), and `missed`.
- Record a completed `payment` debit with metadata suitable for wallet history UI (meal/package, date, lunch/dinner, amount, refs).
- Idempotent under repeated mark / retries.
- Keep delivery mark and debit in one atomic unit of work where payment succeeds.

**Non-Goals:**

- Recalculating ingredient / operational / profit formulas at delivery time (reuse order snapshot).
- Charging at order create or month start.
- Refunds for meal-off / missed (meal-off docs already say no refund in v1; no charge means nothing to refund).
- Live payment gateways, auto-top-up, or allowing negative wallet balances.
- Changing meal-off deadline rules or delivery address resolution.
- Partial per-ingredient customer invoices.

## Decisions

### 1. Price source = order per-meal snapshot (not live cycle recalculation)

- **Choice:** Charge `order.per_meal_price_snapshot` quantized to 2 decimal places.
- **Why:** Matches what the customer bought; admin later changing cycle costs must not rewrite past delivered meals. Snapshot already derives from published final meal price (ingredients + op cost + profit).
- **Alternatives considered:** Live `per_meal_rate` from current finalized plan (unstable); store a separate `charged_amount` on each delivery at generation time (more schema, same number as snapshot for uniform packages).

### 2. Hook point = delivery status transition to `delivered`

- **Choice:** Call a new `orders.services.meal_payment.charge_delivered_meal(delivery)` from `mark_delivery` (and any future deliveryman completion path that ends in the same service) **only when** status changes from non-`delivered` to `delivered`.
- **Why:** Single domain entry point; meal-off already sets `skipped` and never hits this path.
- **Alternatives considered:** Django signal on `OrderDelivery.save` (easy to miss callers / harder to test); async Celery job (eventual consistency risk for duplicate marks).

### 3. Ledger integration via existing `debit_wallet`

- **Choice:** `debit_wallet(..., type=PAYMENT, method=MANUAL, status=COMPLETED, idempotency_key=f"meal-delivery:{delivery.public_id}", metadata={...}, note=human-readable summary)`.
- **Why:** Reuses concurrency (`select_for_update`), frozen checks, and unique idempotency constraint. No new payment table required for v1 if delivery stores FK / public_id of the transaction.
- **Metadata (minimum):** `purpose=meal_delivery`, `order_public_id`, `delivery_public_id`, `service_date`, `meal_period`, `meal_name`, `package`/`meal` label as available from order snapshots.

### 4. Payment outcome fields on `OrderDelivery`

- **Choice:** Add nullable `wallet_transaction` FK (or store `wallet_transaction_public_id` + `payment_status`: `not_applicable` | `charged` | `failed`) updated only by the meal-payment service.
- **Why:** Ops can see whether a delivered slot was paid; duplicate prevention can also check “already charged” without scanning all wallet rows.
- **Default:** `not_applicable` until first `delivered` attempt; `skipped`/`missed` stay `not_applicable`.

### 5. Insufficient funds / frozen wallet on delivery

- **Choice:** **Complete the delivery status change**, then attempt debit inside the same `transaction.atomic()` block. If `InsufficientFundsError` or `WalletFrozenError`: roll back **only the debit** is not possible mid-atomically if we want delivery saved — so either:
  - **Preferred v1:** Keep one atomic block: if debit fails, **abort the whole mark** and return a clear error to admin/deliveryman (`402`/`409`/`422` with code like `WALLET_INSUFFICIENT_FOR_MEAL` / `WALLET_FROZEN`), leaving status `scheduled`. Ops must resolve wallet before marking delivered.
  - Rationale: avoids “delivered but unpaid” debt ledger in v1; aligns with non-negative balance invariant; customers already must hold min balance to order.
- **Alternatives considered:** Mark delivered + `payment_status=failed` (better for real-world “food already handed over”, more follow-up tooling); allow negative balance (breaks existing wallet invariant).

### 6. Wallet history API enrichment

- **Choice:** Extend `WalletTransactionSerializer` to expose a structured `meal_payment` object (or flatten key metadata fields) when `type=payment` and metadata contains meal delivery keys; omit / null for other types.
- **Why:** Frontend can render history without parsing opaque JSON only; still keep raw `metadata` internal or documented as secondary.

### 7. Duplicate prevention

- **Choice:** Combine (a) idempotency key `meal-delivery:{delivery.public_id}`, (b) skip charge if delivery already `delivered` with `payment_status=charged`, (c) existing mark_delivery idempotency for same status.
- **Why:** Defense in depth against double POST and concurrent workers.

## Risks / Trade-offs

- **[Risk] Blocking mark-delivered when wallet is short after food is already given** → Mitigation: document ops process (recharge then mark); consider v2 “delivered + unpaid” if field ops need it; keep min-balance gate strong at order time.
- **[Risk] Historical deliveries marked delivered before this feature** → Mitigation: no backfill charge; only new transitions after deploy.
- **[Risk] Snapshot ≠ current admin “final meal price” display** → Mitigation: document that charge uses purchase-time snapshot; admin costing UI remains planning-only.
- **[Risk] Nested `transaction.atomic` with wallet debit** → Mitigation: call charge inside `mark_delivery`’s existing atomic block; rely on Django savepoint/outer atomic semantics; tests for concurrent mark.
- **[Trade-off] No refunds for mistaken delivered marks** → Correction path is admin adjustment credit (`type=adjustment`) outside this change’s automation; document manually.

## Migration Plan

1. Add `OrderDelivery` payment fields + migration (nullable, default unpaid/not_applicable).
2. Deploy code that charges only on **new** transitions to `delivered`.
3. Update wallet transaction serializers and OpenAPI.
4. Ship backend/frontend docs; run order delivery + wallet tests.
5. **Rollback:** disable charge hook behind a settings flag if needed (`MEAL_DELIVERY_WALLET_CHARGE_ENABLED=True` default on); already-charged rows remain in ledger (do not auto-reverse).

## Open Questions

- None blocking implementation: insufficient-funds policy is decided as “fail the mark, keep scheduled” for v1. Revisit if deliveryman mobile needs post-handover marking without wallet gate.
