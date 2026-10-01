## Context

BeFood already has a mature subscription meal stack:

- **Active entitlement:** `get_active_subscription(customer)` in `orders/services/subscription_service.py` (`status=active`, unique per customer).
- **Slots:** `OrderDelivery` is unique per `(subscription, service_date, meal_period)` with lifecycle `scheduled|delivered|skipped|missed`. Regular meals are **charged on deliver** via `charge_delivered_meal` using published `MonthlyMenuSlot.final_meal_price_snapshot`.
- **Cutoff:** `MealOffSettings` + `is_past_meal_cutoff` / `meal_off_deadline` (Asia/Dhaka by default).
- **Wallet:** `debit_wallet` with `select_for_update`, per-wallet `idempotency_key`, dual buckets (`recharge_balance` / `commission_balance`). Meal-stop uses `OrderWalletSettings.meal_stop_threshold` against spendable balance in existing automation.
- **Kitchen demand:** `orders/services/meal_demand.py` counts **one unit per `OrderDelivery` row** (`Count('id')`)—subscription `quantity` is currently for delivery-fee tiers, not kitchen multiplication.
- **Admin activity:** composed in `user_management/services/admin_customer.build_activity_events` (no write-side activity table).
- **No** existing guest-meal entity, box-price setting, or prepaid guest purchase flow.

Guest Meal must be **prepaid at order time**, quantity-quota’d per calendar month, and still show up for kitchen/rider ops—without duplicating pricing, cutoff, or wallet ledger logic.

## Goals / Non-Goals

**Goals:**

- Active-subscriber-only guest meal purchase for a concrete date + meal period.
- Canonical slot price + configurable box price, snapshotted on purchase.
- Atomic wallet debit + meal-stop floor; monthly quantity cap of 10 (Asia/Dhaka).
- Reuse cutoff, subscription period coverage, published menu resolution.
- Rider/kitchen visibility of guest quantity.
- Preview + create + usage APIs; auditability via wallet ledger + activity composition.
- Concurrency-safe quota and balance enforcement; optional `Idempotency-Key`.

**Non-Goals:**

- Implementing cancellation/refund in this change (design only as open decision).
- Selling guest meals to non-subscribers.
- Hardcoding 10 BDT box price or meal prices in code constants.
- Replacing charge-on-delivery for the subscriber’s regular `OrderDelivery` slot.
- Rewriting historical delivery rows or inventing a second logistics status enum.

## Decisions

### D1 — Data model: dedicated `GuestMealOrder` + optional link to `OrderDelivery` (Option B)

**Choice:** Introduce `orders.GuestMealOrder` (`PublicIdMixin`) as the **source of truth** for guest purchases: customer, subscription, `service_date`, `meal_period`, `quantity`, pricing snapshots (`base_meal_price`, `box_price`, `unit_price`, `total_amount`), `wallet_transaction` FK, status, timestamps, optional `delivery` FK to the subscriber’s regular slot.

**Alternatives considered:**

| Option | Idea | Why rejected / weaker |
|--------|------|------------------------|
| A | Extend only `Order` / inflate delivery | Regular charge-on-delivery vs prepaid guest conflict; historical monthly `Order` is retired for subscribe path |
| C | Only bump quantity on `OrderDelivery` | Unique slot already exists; no place for box/base snapshot, prepaid ledger link, or monthly quota audit without a second record |
| Pure child rows without parent link | Guest-only logistics | Duplicates rider address/zone attribution already on `OrderDelivery` |

**Rationale:** Financial integrity + monthly SUM(quantity) + pricing snapshot require a first-class purchase row. Delivery integration reuses the existing stop via FK / aggregated `guest_quantity` rather than a second stop per guest unit.

### D2 — When no scheduled `OrderDelivery` exists for the slot

**Choice (default for implement):** Guest order is allowed only if:

1. Subscription is active (`get_active_subscription`).
2. Requested `meal_period` ∈ `periods_for_meal_period(subscription.meal_period_snapshot)`.
3. Published schedule/slot exists for the package + date + period with non-null `final_meal_price_snapshot`.
4. Cutoff not passed (`not is_past_meal_cutoff`).
5. Ensure/resolve the subscriber’s `OrderDelivery` for that slot (call existing `ensure_subscription_deliveries` / get-or-create path as used elsewhere) and attach `GuestMealOrder.delivery` to it.

If the regular slot is **customer-skipped (meal OFF)**, default recommendation: **still allow guest purchase** and treat guest quantity as cook/deliver units independent of meal-off of the personal slot—**confirm as open decision**. Until confirmed, implement eligibility that requires a live (non-cancelled-parent) delivery row and document meal-OFF interaction as TBD.

### D3 — Pricing

```
base = MonthlyMenuSlot.final_meal_price_snapshot  # via resolve_published_slot_for_delivery
box  = OrderWalletSettings.guest_meal_box_price   # new field, default 10.00
unit = base + box
total = unit * quantity
```

Reuse `meals.services.slot_pricing.resolve_published_slot_for_delivery`. Reject with clear validation if slot/price missing. Persist all four money fields as Decimal snapshots on `GuestMealOrder`.

### D4 — Monthly limit

- Default `monthly_limit = 10` (also store on settings as `guest_meal_monthly_limit` for admin change without redeploy).
- **Source of truth:** `SUM(quantity)` of guest orders in countable statuses for calendar month of `created_at` (or `service_date`?—see open question; **recommend `created_at` in Asia/Dhaka** so “ordered this month” matches UX; alternatively `service_date` if product wants “meals for dates in month”).
- Countable default: successfully created / paid (`status` in `{scheduled, delivered}` or single `confirmed` + delivery lifecycle). Failed attempts never persist. Cancelled+refunded restore is open decision.
- **No lone mutable counter** as sole truth; optional denormalized monthly cache only if locked transactionally with the SUM check.

### D5 — Wallet & meal-stop floor

Inside `transaction.atomic()`:

1. `select_for_update` wallet (via `debit_wallet`) and lock customer/subscription row as needed.
2. Recompute monthly used from locked guest rows (or `select_for_update` on existing month rows).
3. Validate `post_balance_floor`: product formula stated as  
   `recharge_balance - total >= meal_stop_threshold`  
   Existing meal-stop automation uses **total spendable** `wallet.balance`. **Recommend implementing the product’s recharge formula for guest purchase gate**, while debit strategy for the charge itself should match other meal spends (**commission_first** via `WalletTransaction.Type.PAYMENT`) unless product insists recharge-only. Document mismatch as open decision if finance wants recharge-only debit.
4. `debit_wallet(..., idempotency_key=..., metadata={purpose: guest_meal, ...})`.
5. Create `GuestMealOrder` linked to txn; if either step fails, roll back both.

Do **not** manually mutate balance fields.

### D6 — Cutoff & eligibility reuse

Reuse only:

- `get_active_subscription`
- `business_today` / `meal_off_business_now`
- `periods_for_meal_period`
- `published_schedule_for_meal` / `resolve_published_slot_for_delivery`
- `is_past_meal_cutoff` (at-or-before deadline still eligible, same as meal-off)

No second cutoff calculator.

### D7 — API surface (customer JWT)

Under `/api/v1/` (shared; lean mobile-friendly payloads):

| Method | Path | Role |
|--------|------|------|
| `GET` | `/guest-meals/usage/` | Monthly limit / used / remaining |
| `POST` | `/guest-meals/preview/` | Read-only quote + eligibility (no debit) |
| `POST` | `/guest-meals/` | Create + debit |
| `GET` | `/guest-meals/` | List own guest orders (paginated) |
| `GET` | `/guest-meals/{public_id}/` | Detail |

Client body for preview/create: `{ "date", "meal_period", "quantity" }` only.

Optional header: `Idempotency-Key` on create (wallet unique constraint pattern).

Preview MUST re-run all validations on create; never treat preview as authorization.

Admin settings: extend existing order-wallet settings PATCH to include `guest_meal_box_price` (+ optional `guest_meal_monthly_limit`).

### D8 — Delivery / rider / kitchen

- Aggregate `guest_quantity = SUM(GuestMealOrder.quantity)` for orders linked to an `OrderDelivery` (and/or same customer+date+period) where guest status is still due.
- Expose `guest_quantity` (and optionally `total_servings = 1 + guest_quantity` or `subscription.quantity + guest_quantity`—**open**: subscription quantity vs kitchen today counts 1 per row) on:
  - deliveryman today-board serializers
  - admin today-board if applicable
  - meal demand: add guest units into `expected_meal_count` / `final_cooking_count` for non-cancelled guest orders on that slot
- Marking the parent `OrderDelivery` delivered does **not** re-charge guest meals (already prepaid). Regular slot still uses `charge_delivered_meal` for the subscriber meal only.
- Guest fulfillment status: either mirror parent delivery status or maintain simple `GuestMealOrder.status` updated when parent is delivered/skipped/missed—prefer updating guest rows when parent logistics complete to keep history clear.

### D9 — Activity / admin

Extend `build_activity_events` to emit `guest_meal_ordered` from `GuestMealOrder` rows (composed read model—consistent with existing pattern). Wallet txn already appears as `wallet_transaction_completed`.

### D10 — Concurrency & idempotency

- Single atomic service `create_guest_meal_order(...)`.
- Lock order: wallet `select_for_update` (inside debit) + `select_for_update` on customer’s guest orders for the month (or advisory lock on `CustomerProfile` / subscription row) before quota check.
- Idempotency: `Idempotency-Key` → wallet txn unique; on replay return original guest order. Same key + different payload → `409`.
- Without key: rely on DB transaction + locks; clients SHOULD send keys for mobile retries.

### D11 — Files to touch (planned)

**Create**

- `orders/models.py` — `GuestMealOrder` (+ migration)
- `orders/services/guest_meal.py` — eligibility, pricing, quota, create/preview
- `orders/api/guest_meal_serializers.py`, `guest_meal_views.py` (or section in subscription urls)
- `orders/tests/test_guest_meal.py` (+ concurrency tests)
- `orders/docs/backend/guest-meal-order.md`, `orders/docs/frontend/guest-meal-order.md`

**Modify**

- `orders/models.py` — `OrderWalletSettings.guest_meal_box_price`, `guest_meal_monthly_limit`
- `orders/services/order_wallet_settings.py`, wallet-settings serializers/views
- `orders/services/meal_demand.py` — include guest quantities
- Delivery board serializers (orders / user_management / delivery_zones as used by today-board)
- `wallet/models.py` — optional new `WalletTransaction.Type.GUEST_MEAL_PAYMENT` **or** reuse `PAYMENT` + metadata `purpose=guest_meal` (prefer **reuse PAYMENT + metadata** to avoid enum churn; document purpose)
- `user_management/services/admin_customer.py` — activity event
- `wallet/services/ledger.py` — only if new type needs debit strategy mapping
- URL routers in `orders/api/urls.py`

## Risks / Trade-offs

- **[Risk] Meal demand historically = Count(OrderDelivery)** → guest units invisible to kitchen → Mitigation: explicitly add SUM(guest quantity) into demand + document invariant change.
- **[Risk] Double charge if guest linked to delivery and someone charges guest again on deliver** → Mitigation: guest prepaid only; `charge_delivered_meal` never reads guest rows.
- **[Risk] Race on monthly cap 9→11** → Mitigation: transactional lock + re-SUM inside atomic block; concurrency tests.
- **[Risk] Recharge vs spendable threshold mismatch** → Mitigation: open decision; document chosen formula in API errors.
- **[Risk] Meal OFF + guest still cook** confuses riders → Mitigation: board shows `guest_quantity` separately; open product rule.
- **[Risk] Idempotency without client key** → Mitigation: document required header for create; still lock wallet/quota.

## Migration Plan

1. Additive migrations: settings fields (defaults `box=10.00`, `limit=10`), `GuestMealOrder` table.
2. Deploy backend with APIs behind feature readiness; no backfill required.
3. Wire mobile/web to usage → preview → create.
4. Rollback: disable routes / feature flag if added; table can remain empty. Do not remove money ledger rows.

## Open Questions

Resolved for v1 implementation (product may revise later):

1. **Cancellation / refund:** Out of scope for v1 (no cancel/refund API).
2. **Quota month basis:** Asia/Dhaka calendar month of `created_at`.
3. **Meal OFF interaction:** Allow guest purchase even when personal slot is skipped; guest units still count toward kitchen cooking.
4. **Balance floor:** Enforce `recharge_balance - total >= meal_stop_threshold` (inclusive floor) at purchase time.
5. **Debit strategy:** `PAYMENT` + commission_first (same as meal delivery payment).
6. **Kitchen servings:** Regular stop = existing board `meal_quantity` (typically 1); add `guest_quantity` separately; demand adds guest SUM to expected/cooking.
7. **Per-request max quantity:** `min(10, monthly_limit, remaining)`.
8. **Past dates:** Reject `date < business_today`.
9. **Admin create on behalf:** No.
10. **Notifications:** No dedicated guest-meal push/inbox in v1.

Historical open questions kept for future product revision only.

## Recommended Implementation Order

1. Settings fields + docs stub.
2. `GuestMealOrder` model + migration.
3. Pure services: price resolve, quota SUM, eligibility (no API).
4. Atomic create + wallet debit + tests (money + quota + concurrency).
5. Preview/usage/list/create APIs + OpenAPI.
6. Delivery board + meal demand guest quantity.
7. Admin activity + Customer 360 mention.
8. Frontend/backend docs; full test matrix.
