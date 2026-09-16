## Context

Live failure (Postgres):

```text
POST /api/v1/subscriptions/{id}/deliveries/{id}/meal-off/
→ 500 NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join
```

Stack: `subscription_views.meal_off` → `customer_meal_off` →

```python
OrderDelivery.objects.select_for_update().select_related(
    'order', 'order__customer', 'subscription', 'subscription__customer',
).get(pk=delivery.pk)
```

After subscription-based meals, both `OrderDelivery.order` and `OrderDelivery.subscription` are **nullable**. Django `select_related` on nullable FKs emits `LEFT OUTER JOIN`. PostgreSQL forbids `FOR UPDATE` on the nullable side of an outer join — so the query fails even when the row’s non-null parent is `subscription` (order NULL) or vice versa.

Legacy order meal-off uses the same helper, so the bug is shared. Existing tests may look green if they never hit this query shape under Postgres, or if subscription coverage is thin; the production subscription path always hits it.

Meal-off/on product rules (deadlines, ownership, skip_source, wallet) are fine — only the lock query is broken.

## Goals / Non-Goals

**Goals:**

- Meal-off and meal-on succeed for subscription-owned and order-owned slots on PostgreSQL
- Keep row-level locking so concurrent meal-off/on on the same delivery serialize
- No HTTP/API contract change
- Automated regression that fails if `select_for_update` + nullable outer join returns

**Non-Goals:**

- Changing deadline settings, wallet debit rules, or cancel/system skip behaviour
- Schema changes to make `order`/`subscription` non-null
- Frontend changes

## Decisions

### 1. Lock only the delivery row (`of=('self',)`)

- **Choice:** Use `OrderDelivery.objects.select_for_update(of=('self',)).select_related(...)` in both `customer_meal_off` and `customer_meal_on` (Django supports `of` on PostgreSQL).
- **Why:** Keeps one round-trip and eager parents for ownership checks (`delivery_customer`, cancel checks) while Postgres locks only `orders_orderdelivery`, not outer-joined nullable parents.
- **Alternatives:**
  - Lock without `select_related`, then fetch parents in a second query — also correct, slightly more queries
  - Drop `select_for_update` — loses concurrency safety; rejected
  - Make FKs non-null / split tables — out of scope

### 2. Shared lock helper (optional small refactor)

- **Choice:** Prefer a private `_lock_delivery_for_meal_toggle(pk)` used by meal-off and meal-on to avoid duplicating the fragile pattern.
- **Why:** Single place to keep `of=('self',)` + `select_related` correct

### 3. Tests must cover subscription API path on Postgres

- **Choice:** Add/extend tests that `POST .../subscriptions/.../meal-off` (and meal-on) return 200 and update status; assert no `NotSupportedError`. Keep existing order-path meal-off tests.
- **Why:** User’s failure was on the subscription mount; service-level call alone is necessary but API regression is the real contract

## Risks / Trade-offs

- [`of=('self',)` unsupported on some DB backends] → Mitigation: project uses PostgreSQL in local/prod; document Postgres requirement; if SQLite ever used in unit tests, Django may ignore or no-op `of` — still validate on Postgres
- [Related rows not locked] → Acceptable: we only mutate the delivery (and then optionally lock order separately via existing `complete_order_if_done` / `reopen_order_after_meal_on` which already `select_for_update` the order)
- [Hidden copies of the bad pattern elsewhere] → Grep `select_for_update` + nullable `select_related` in orders app; fix only meal-off/on in this change unless identical 500s appear

## Migration Plan

1. Patch `meal_off.py` lock queries
2. Add subscription meal-off/on regression tests; run `orders.tests.test_customer_meal_off` + subscription meal-off cases on Postgres
3. Deploy; smoke POST meal-off from customer SPA
4. Rollback: revert the one service change (no migrations)

## Open Questions

- None blocking. Prefer `select_for_update(of=('self',))` over two-step fetch unless implementation discovers a Django version quirk.
