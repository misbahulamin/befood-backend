## Context

Live failure (Postgres) from admin subscription detail:

```text
POST /api/v1/web/subscriptions/{id}/deliveries/{id}/mark
→ 500 NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer join
```

Stack: `subscription_views.mark_delivery` → `orders.services.order_delivery.mark_delivery` →

```python
OrderDelivery.objects.select_for_update()
.select_related(
    'order',
    'subscription',
    'subscription__customer',
    'order__customer',
).get(pk=delivery.pk)
```

After subscription-based meals, both `OrderDelivery.order` and `OrderDelivery.subscription` are **nullable**. Django `select_related` on nullable FKs emits `LEFT OUTER JOIN`. PostgreSQL forbids `FOR UPDATE` on the nullable side of an outer join — so the query fails for subscription-owned slots (`order` NULL) and would also fail for order-owned slots with nullable `subscription`.

Customer meal-off/on already fixed this via `select_for_update(of=('self',))` in `meal_off._lock_delivery_for_meal_toggle` (`fix-meal-off-select-for-update-outer-join`). That change explicitly deferred the same pattern in `order_delivery.py` and `meal_payment.py`. Admin mark now hits those deferred sites.

`mark_delivery` also calls `charge_delivered_meal` on transition to `delivered`. That helper uses the same broken lock shape, so fixing only `mark_delivery` would leave delivered marks still failing at charge time.

Product rules for mark (status machine, wallet debit, skip_source=admin, completion) are fine — only the lock queries are broken.

## Goals / Non-Goals

**Goals:**

- Admin mark `delivered` and `skipped` succeed for subscription-owned and order-owned slots on PostgreSQL
- Delivered marks still run wallet charge without a second FOR UPDATE outer-join 500
- Keep row-level locking so concurrent marks on the same delivery serialize
- No HTTP/API contract change
- Automated regression that fails if the bad lock pattern returns
- Zero behaviour change for customer meal-off/on

**Non-Goals:**

- Changing customer meal-off/on helpers, deadlines, or skip_source rules
- Changing wallet amounts, idempotency keys, or payment business rules
- Schema changes to make `order`/`subscription` non-null
- Frontend / admin UI changes
- Broad refactor of all `select_for_update` in the repo (only the two failing call sites)

## Decisions

### 1. Use the established `of=('self',)` pattern (match meal-off)

- **Choice:** Change both lock sites to `select_for_update(of=('self',))` while keeping existing `select_related(...)` for parent/customer checks.
- **Why:** Already proven in `meal_off.py` and `delivery_address.py`; one round-trip; Postgres locks only `orders_orderdelivery`.
- **Alternatives:**
  - Lock without `select_related`, then fetch parents — also correct, more queries
  - Drop `select_for_update` — loses concurrency safety; rejected
  - Make FKs non-null — out of scope; would break subscription/order dual parent model

### 2. Fix both `mark_delivery` and `charge_delivered_meal` in one change

- **Choice:** Patch `order_delivery.mark_delivery` and `meal_payment.charge_delivered_meal` together.
- **Why:** Admin mark `delivered` always chains into charge; fixing only the first lock leaves skip working but deliver still 500ing.
- **Alternatives:** Fix mark only first — incomplete for the admin “delivered” action the user reported.

### 3. Do not touch `meal_off.py` or customer endpoints

- **Choice:** Leave customer meal toggle code and APIs unchanged.
- **Why:** User constraint: do not create new customer issues; meal-off/on already works.

### 4. Tests cover subscription admin mark on Postgres

- **Choice:** Add/extend service or API tests for `POST .../web/subscriptions/.../deliveries/.../mark` with `delivered` and `skipped`; assert no `NotSupportedError`. Keep existing order-owned mark tests green.
- **Why:** Failure was on the web subscription mount with a subscription-owned delivery.

## Risks / Trade-offs

- [`of=('self',)` unsupported on some DB backends] → Mitigation: project uses PostgreSQL in local/prod; SQLite tests may ignore `of` — still validate on Postgres
- [Related parent rows not locked] → Acceptable: we mutate the delivery first; order completion already locks the order separately where needed
- [Changing charge lock subtly] → Mitigation: only change lock clause; no payment rule edits; run existing `test_meal_delivery_wallet_payment` suite
- [Scope creep into meal-off] → Explicit non-goal; do not edit `meal_off.py`

## Migration Plan

1. Patch `select_for_update(of=('self',))` in `mark_delivery` and `charge_delivered_meal`
2. Add subscription admin mark regression tests; run related orders tests on Postgres
3. Deploy; smoke admin panel mark delivered + skip on a subscription delivery
4. Rollback: revert the two service lock lines (no migrations)

## Open Questions

- None blocking. Prefer matching meal-off’s `of=('self',)` exactly over extracting a shared cross-module helper unless duplication becomes painful during apply.
