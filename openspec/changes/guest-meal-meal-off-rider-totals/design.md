# Design

## Context

See proposal.md for motivation. Audit of the shipped Guest Meal stack (read-only; no code changed in this planning change):

| Area | Observed implementation | Finding |
|------|-------------------------|---------|
| Eligibility | `orders/services/guest_meal.py` `build_guest_meal_quote` (~278–358) | Checks active sub, past date, preference periods, `is_past_meal_cutoff`, published price, quota, recharge floor. **Does not** check personal Meal-OFF. |
| Prior product decision | `openspec/changes/guest-meal-order-system/design.md` | Explicitly allowed guest purchase when personal slot is skipped. **Superseded** by this change. |
| Meal-OFF SoT | `OrderDelivery` + `orders/services/meal_off.py` `customer_meal_off` (~243–298) | Customer OFF → `status=skipped`, `skip_source=customer`. Admin/system also use `skipped` with other `skip_source` values (`CUSTOMER`/`ADMIN`/`SYSTEM` in `orders/models.py` ~322–325). `can_meal_on` only undoes `skip_source=customer`. |
| Delivery link | `_resolve_linked_delivery` (~265–275) | Calls `ensure_subscription_deliveries` then `.first()`; **nullable** FK on `GuestMealOrder.delivery` (`SET_NULL`). Create can succeed with `delivery=None`. |
| Rider board | `delivery_zones/services/board.py` (~448–449) | Emits `meal_quantity` (regular via `_meal_quantity`) + `guest_quantity` (batch `guest_quantities_by_delivery_ids`). **No** `total_meal_quantity`. Board statuses are scheduled/delivered only — skipped parents disappear. |
| Rider summary | `delivery_zones/services/today_summary.py` (~88–127) | Counts **stops**, not meal boxes; no guest/regular/total box metrics. |
| Wallet | `create_guest_meal_order` + `debit_wallet` | Atomic; wallet `select_for_update`; month rows locked; floor uses `recharge_balance`; PAYMENT defaults to `commission_first`. Docs claim commission_first — matches ledger default. |
| Deliver charge | `charge_delivered_meal` + `sync_guest_meals_for_delivered_delivery` | Regular charge only; guests flipped to delivered on parent deliver (`order_delivery.py` ~295–297). |
| Docs | `orders/docs/GUEST_MEAL_INTEGRATION_GUIDE.md` | Lists cutoff eligibility; says riders should add `guest_quantity` to `meal_quantity`; no `PERSONAL_MEAL_OFF`; no Meal-OFF block. |

**Confirmed gaps / bugs (vs updated requirements):**

1. Personal Meal-OFF does not block Guest Meal preview/create.
2. Paid Guest Meal can be created with `delivery=null` if stop resolution fails.
3. After customer Meal-OFF, skipped parent leaves scheduled Guests invisible on rider board (orphan/ops risk); v1 has no cancel/refund.
4. Rider APIs lack server `total_meal_quantity` and summary box reconciliation.
5. Documentation / prior OpenSpec decision conflict with the new Meal-OFF rule.

**Potential issues (verify in WP tests, not claimed broken without repro):**

- Floor uses recharge-only while debit may consume commission first → customer can pass floor yet still debit differently; document and keep policy unless product changes.
- Concurrent Meal-OFF vs create without locking the delivery row in guest create.
- Subscription date far outside `ensure_subscription_deliveries` horizon → null delivery path.
- Admin today-board serializers (`orders/api/serializers.py` guest_quantity) may need the same total field for parity.

## Goals / Non-Goals

**Goals:**

- Authoritative personal Meal-OFF gate on preview + create with create-time revalidation.
- Prevent Meal-OFF when scheduled Guest Meals exist for that slot.
- Reject create when delivery stop cannot be linked (no paid orphans).
- Additive rider box totals + summary metrics that reconcile with board scope.
- Regression matrix covering eligibility, wallet, delivery, rider, docs/OpenAPI.

**Non-Goals:**

- Implementing Guest Meal cancel/refund.
- Changing commission_first / recharge floor formulas without an explicit product change.
- Reopening/editing completed change `guest-meal-order-system` in place.
- Making `GuestMealOrder.delivery` non-null via migration in v1 of this fix (prefer reject-at-create; optional later constraint).

## Decisions

### D1 — Personal Meal-OFF source of truth

**Choice:** Treat personal OFF as: subscription `OrderDelivery` for `(customer/subscription, service_date, meal_period)` with `status=skipped` AND `skip_source=customer`.

**Alternatives:** (a) any `skipped`; (b) preference flags unrelated to delivery. Rejected — audit shows `skipped` also means admin/system (cancel, cutoff_passed).

**Implementation sketch:** Helper e.g. `is_personal_meal_off(customer, service_date, meal_period)` used by `build_guest_meal_quote`. Prefer resolving via active subscription delivery row (create path already ensures deliveries). If no row yet and ensure would create `scheduled`, treat as ON for this gate; if ensure would create system-skipped past cutoff, cutoff gate already rejects.

### D2 — Error contract

**Choice:** `GuestMealNotEligibleError(..., code='PERSONAL_MEAL_OFF')` → existing `_guest_meal_error_response` → HTTP 422 `{detail, error_code}`.

Message: `Guest Meal cannot be ordered because your regular meal is OFF for this date.`

### D3 — Create-time locking vs Meal-OFF races

**Choice:** Inside `create_guest_meal_order` atomic block, after wallet lock / before debit: `select_for_update(of=('self',))` on the target `OrderDelivery` (same pattern as `_lock_delivery_for_meal_toggle`), re-check personal OFF + status must be `scheduled` for create, then debit + create with `delivery=locked`.

**Meal-OFF path:** In `customer_meal_off`, after locking delivery, reject if countable `GuestMealOrder` exists for that delivery / slot (`status=scheduled`). Also update `can_meal_off` to return false when such guests exist.

### D4 — Missing delivery stop

**Choice:** If after `ensure_subscription_deliveries` no row exists for the slot, raise eligibility/validation error (e.g. `DELIVERY_UNAVAILABLE`) and abort before debit. Do not persist `delivery=null` on success path.

**Alternatives:** Auto-create outside horizon; accepted only if product expands horizon — out of scope.

### D5 — Rider totals

**Choice:**

- Keep `meal_quantity` = `_meal_quantity(delivery)` (regular only).
- Keep `guest_quantity` = SUM countable guests for delivery.
- Add `total_meal_quantity = meal_quantity + guest_quantity`.
- today-summary: add meal-box metrics derived from the same scoped queryset + guest aggregation (e.g. `regular_meal_quantity`, `guest_meal_quantity`, `total_meal_quantity`, plus `delivered_meal_quantity` / `pending_meal_quantity`). Preserve existing stop-count fields (`total`/`delivered`/`pending`) for compatibility; document that new fields are box counts.

**Double-count guard:** Never fold guest into `meal_quantity`. Package `packages[].count` remains stop-based unless a later change redefines it.

### D6 — OpenSpec strategy

**Choice:** New change `guest-meal-meal-off-rider-totals`. Do not mutate completed `guest-meal-order-system`. Note that guest-meal specs were never synced to `openspec/specs/`; this change introduces corrected capabilities for eventual archive/sync.

### D7 — Work packages (implementation order)

1. WP-01/02 eligibility + Meal-OFF SoT + create locking  
2. WP-03 delivery link reject-if-missing  
3. WP-04/05 rider board + summary  
4. WP-06 wallet/idempotency regression hardening (no policy change unless tests prove bug)  
5. WP-07 tests  
6. WP-08 docs/OpenAPI  

## Risks / Trade-offs

- **[Risk] Customers with historical Guest Meals on already-skipped parents** → Mitigation: do not auto-refund; ops runbook; optional admin list later. New purchases blocked; new Meal-OFF blocked when guests exist.
- **[Risk] Express clients ignore new total fields** → Mitigation: additive fields; keep docs that clients may sum; prefer server total going forward.
- **[Risk] Deadlock wallet vs delivery lock order** → Mitigation: document lock order: wallet → month guest rows → delivery (or delivery before debit consistently); never reverse in meal-off vs guest paths without shared helper.
- **[Risk] Summary stop counts vs box counts confuse clients** → Mitigation: distinct field names + docs.
- **[Trade-off] Blocking Meal-OFF until cancel/refund exists** → Stricter UX now; safer than invisible paid boxes.

## Migration Plan

1. Ship code + tests; no required schema migration for reject-at-create + additive JSON fields.
2. Optional follow-up: non-null `delivery` constraint + data repair for legacy null-delivery rows (out of initial WP).
3. Update customer + rider clients for `PERSONAL_MEAL_OFF` and Meal-OFF blocked-when-guest.
4. Rollback: revert deploy; additive API fields are safe to leave; removing Meal-OFF gate would restore old purchase behavior.

## Open Questions

None that block specs/tasks. Assumed answers recorded above: personal OFF = customer skip only; block Meal-OFF when scheduled guests exist; reject create if delivery missing; keep stop-count summary fields and add box-count fields.
