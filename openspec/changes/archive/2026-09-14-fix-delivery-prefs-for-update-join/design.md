## Context

Live failure (Postgres):

```text
PUT /user_management/customer/delivery-preferences/
→ 500 NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join
```

Stack: `MealDeliveryPreferenceView.put` → `resync_future_scheduled_deliveries` →

```python
OrderDelivery.objects.select_related('order', 'subscription')
    .filter(status=SCHEDULED, service_date__gte=today)
    .filter(Q(order__customer=...) | Q(subscription__customer=...))
    .select_for_update()
```

`OrderDelivery.order` and `OrderDelivery.subscription` are both nullable. Filtering across either parent and `select_related` on those FKs emit LEFT OUTER JOINs. PostgreSQL forbids `FOR UPDATE` on the nullable side of an outer join, so the queryset fails before any snapshot update runs.

The same day-override PUT path also calls `resync_future_scheduled_deliveries` and will 500 the same way. Preview does not call resync, which is why preview returned 200 while preference save failed.

This is the same Postgres constraint previously fixed for meal-off via `select_for_update(of=('self',))` in `orders/services/meal_off.py`. Product rules for address resync (future `scheduled` only) are fine — only the lock query is broken.

## Goals / Non-Goals

**Goals:**

- Preference and day-override saves succeed when the customer has future scheduled deliveries (order-owned, subscription-owned, or mixed) on PostgreSQL
- Keep row-level locking on `OrderDelivery` so concurrent preference saves / resyncs serialize on those rows
- No HTTP/API contract change
- Automated regression that fails if bare `select_for_update()` + nullable outer join returns in this path

**Non-Goals:**

- Changing resolution precedence, snapshot field set, or which statuses are resynced
- Schema changes to make `order` / `subscription` non-null
- Fixing other `select_for_update` + nullable join call sites unless they fail the same way in this change’s scope (note them for follow-up)
- Frontend changes

## Decisions

### 1. Lock only the delivery row (`of=('self',)`)

- **Choice:** Change `resync_future_scheduled_deliveries` to use `.select_for_update(of=('self',))` while keeping `select_related('order', 'subscription')` for efficient parent access in `resolve_and_apply_snapshot`.
- **Why:** Matches the proven meal-off fix; one round-trip; Postgres locks only `orders_orderdelivery`, not outer-joined nullable parents.
- **Alternatives:**
  - Two-step: fetch PKs without lock, then `select_for_update(of=('self',)).filter(pk__in=...)` without joining — also correct, more queries / more code
  - Drop `select_for_update` — loses concurrency safety; rejected
  - Split OR filter into two locked queries (order-owned ∪ subscription-owned) — works but duplicates logic and still needs `of=('self',)` if any join remains

### 2. Keep OR ownership filter as-is

- **Choice:** Retain `Q(order__customer=...) | Q(subscription__customer=...)` so both parent types are covered in one queryset.
- **Why:** Behaviour already matches product intent; only the lock clause needs fixing.

### 3. Tests must hit the lock path under Postgres

- **Choice:** Extend service or API tests so preference PUT (or direct `resync_future_scheduled_deliveries`) runs against a customer with at least one future `scheduled` delivery that has a nullable parent (subscription-owned with `order` null, or order-owned with `subscription` null). Assert success and updated snapshot; assert no `NotSupportedError`.
- **Why:** Existing resync tests may pass if they never combined the lock with the join shape under Postgres.

## Risks / Trade-offs

- [`of=('self',)` Postgres-oriented] → Mitigation: project uses PostgreSQL in local/prod; same pattern already shipped for meal-off
- [Related order/subscription rows not locked] → Acceptable: resync only mutates delivery snapshot fields
- [Same anti-pattern elsewhere] → Grep noted sites (`meal_payment.py`, `order_delivery.py`, etc.); out of scope unless identical 500s appear during this work — document in tasks notes
- [OR filter still produces outer joins] → `of=('self',)` is required specifically because those joins remain; do not “fix” by removing joins without replacing lock safety

## Migration Plan

1. Patch `orders/services/delivery_address.py` lock clause
2. Add/extend regression test; run delivery-address tests on Postgres
3. Deploy; smoke PUT delivery-preferences from SPA
4. Rollback: revert the one service change (no migrations)

## Open Questions

- None blocking. Prefer `select_for_update(of=('self',))` consistent with meal-off unless implementation finds a Django quirk on list iteration (if so, fall back to PK list then lock-by-pk).
