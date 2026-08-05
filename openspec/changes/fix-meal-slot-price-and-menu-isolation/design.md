## Context

Today’s delivery charge path (`orders/services/meal_payment.charge_delivered_meal`) debits `Order.per_meal_price_snapshot`. That value is frozen at order create from `MealCategory.total_price / expected_servings` — i.e. the package **average** meal rate from cycle finalize (`MealCyclePlan.snapshot_per_meal_rate` / published `total_price`).

Admins already have the correct **per-serving** formula via `build_one_meal_price_preview`:

```text
final_meal_price = Σ(ingredient unit costs) + per_meal_operational_cost + profit
```

but `MonthlyMenuSlot` only stores date, period, and ingredient FKs — **no price snapshot**. So delivery cannot charge the actual lunch vs dinner menu for that day.

Menu data model is already package×month keyed (`MealCycle` → `MealCyclePlan` unique per category → `MonthlyMenuSchedule` OneToOne). Publish itself only flips one schedule’s status. Reported cross-package menu loss may be: sync `apply` overwriting a target, reopen deleting a draft schedule, list/filter confusion, or frontend state keyed only by month. Finalized **plan** snapshots ignore live ingredient edits; **slot** prices still recalculate from live ingredients if previewed — so “July menu stays 65 after August chicken price change” is **not** guaranteed for per-slot charges until we snapshot slot prices at publish.

Stakeholders: kitchen/admin (menu publish), finance (correct debit), customers (wallet history), frontend (display chargeable amounts).

## Goals / Non-Goals

**Goals:**

- Charge the delivered lunch/dinner **slot final selling price**, not package average.
- Snapshot that price (and cost breakdown) per slot at publish time; keep it immutable while published.
- Prove package×month isolation with tests and fix any real cross-write bugs (sync, reopen, API filters).
- Document average rate as reference-only; update frontend instructions for API/UI changes.
- Preserve existing idempotent wallet debit behavior (one charge per delivery).

**Non-Goals:**

- Redesigning cycle plan package rollup / `per_meal_rate` math for marketing display.
- Changing meal-off / skip / missed (still no charge).
- Rebuilding the full admin menu UI.
- Refunds/reversals for already-charged average-rate deliveries (one-time ops decision if needed).
- Making order eligibility min-balance equal sum of all slot prices (see decisions — keep average estimate unless product insists).

## Decisions

### D1: Source of charge amount = published slot snapshot

**Choice:** At delivery, resolve the order’s meal package + delivery `(service_date, meal_period)` → that package’s published `MonthlyMenuSlot` → debit `slot.final_meal_price_snapshot` (new field). Persist the charged amount also on `OrderDelivery` (e.g. `charged_amount`) for audit.

**Why not keep order average?** Product explicitly rejected average; lunch 62 vs dinner 38 must differ.

**Why not live-recalculate at delivery?** Would break immutability when ingredients change mid-month; also conflicts with “finalized menu price fixed.”

**Fallback:** If no published slot / missing snapshot (data hole), reject mark-delivered with a clear validation error (do not silently fall back to average). Optional ops flag only if needed later.

### D2: When to compute and freeze slot prices

**Choice:** On `publish_schedule`, for every non-empty slot, compute final price using the same formula as `build_one_meal_price_preview`, with:

- ingredient unit costs from **current** catalog at publish time (or from plan-line snapshots if we add line unit-cost snapshots — prefer catalog at publish + store numbers on the slot),
- `per_meal_operational_cost` resolved for the cycle year/month (same as plan),
- `profit_percent` from the linked `MealCyclePlan`.

Store on `MonthlyMenuSlot`:

- `final_meal_price_snapshot`
- `ingredient_cost_snapshot`
- `operational_cost_snapshot`
- `profit_snapshot`
- optionally JSON `ingredient_cost_lines` for audit

Clear or recompute only on unpublish → edit → republish of **that** schedule.

**Why publish-time not assignment-save?** Draft menus may churn; publish is the kitchen lock point and matches “finalize then publish menu” mental model. Plan finalize remains package-level; slot prices lock at menu publish.

### D3: Average rate remains for display / eligibility

**Choice:**

| Use | Field | Role after this change |
|-----|--------|-------------------------|
| Package marketing / offering | `per_meal_rate` | Estimated average — label as estimate |
| Order create snapshot | `per_meal_price_snapshot` | Keep for eligibility / historical package estimate; **not** delivery debit |
| Delivery debit | slot `final_meal_price_snapshot` | Authoritative charge |
| Wallet history amount | ledger `amount` | Equals slot snapshot |

Order eligibility min balance stays based on average × remaining meals (or existing rule) unless product later requires max slot or first-N sum — document as open product follow-up.

### D4: Package×month isolation

**Choice:** Treat model uniqueness as the source of truth; add regression tests:

1. Publish package A July → package B July schedule unchanged (status, slots, prices).
2. `replace_schedule_assignments` / delete / unpublish scoped to one schedule public_id.
3. `apply_sync` only mutates the **explicit target** schedule and never other packages.
4. Reopen plan deletes only **that** plan’s draft schedule (existing behavior) — never sibling packages.
5. Customer/admin list endpoints filter by `plan` / `meal_category` + cycle, never “one schedule per month globally.”

Investigate any API that returns a single schedule per month without package id; fix filter/serializer if found. Document frontend: cache keys MUST include `meal_public_id` + `year` + `month`.

### D5: Ingredient delete / price change after publish

**Choice:**

- Published slot prices **never** recompute from live ingredients.
- `Ingredient` delete remains `PROTECT` on slot items (already) so deletes cannot cascade-wipe menus.
- Live price updates affect draft previews and future publishes only.
- Admin unpublish + republish is the only way to refresh slot prices for that package/month.

### D6: Delivery → slot resolution

**Choice:** Look up schedule via `published_schedule_for_meal(order.meal_id, year, month)` then slot by `(service_date, meal_period)`. If order spans a month without a published menu, reject charge (consistent with existing order-month publish gates where applicable).

Store `final_meal_price` (and maybe breakdown) in wallet transaction metadata for transparency.

### D7: API / frontend contract

**Additive fields (preferred, minimize BREAKING response shape):**

- Admin schedule assignment/detail: per slot `final_meal_price` (null while draft; set after publish).
- Delivery mark response: `charged_amount`, `payment_status` (existing).
- Customer package menu: optional `final_meal_price` per slot when published (product may hide from customers — expose to admin first; customer optional).

**BREAKING behavior:** same delivery may charge different amounts for lunch vs dinner; clients that assume constant debit = `per_meal_price_snapshot` must update.

## Risks / Trade-offs

- [Historical orders charged at average] → Mitigation: no automatic rebill; document; ops manual adjust if required.
- [Missing slot snapshot blocks delivery] → Mitigation: publish must write all slot prices; migration backfill for already-published schedules; admin alert on incomplete snapshots.
- [Publish slower for full month] → Mitigation: bulk compute in one transaction; ~62 slots trivial.
- [Eligibility vs actual spend diverges] → Mitigation: docs + optional future eligibility using max/sum of slot prices.
- [Sync apply still confuses admins] → Mitigation: keep sync explicit; UI warning; tests that sync never touches non-target packages.
- [Dual price fields confuse UI] → Mitigation: frontend doc labels “estimated average” vs “this meal charge.”

## Migration Plan

1. Add nullable snapshot columns on `MonthlyMenuSlot` (+ optional `OrderDelivery.charged_amount`).
2. Data migration: for each **published** schedule, recompute and fill slot snapshots from current ingredients + plan profit + month op cost (best-effort freeze going forward).
3. Deploy code: publish writes snapshots; charge reads snapshots; reject if null.
4. Update docs + frontend instructions.
5. Rollback: feature flag to temporarily charge `per_meal_price_snapshot` again if critical production issue (default off after validation). Prefer flag over silent dual behavior in steady state.

## Open Questions

1. Should customer-facing package menu show `final_meal_price` per slot, or admin-only?
2. Should order eligibility switch from average to “sum of remaining published slot prices” in this change or a follow-up?
3. For already-delivered meals charged at average, is any correction required?
4. On unpublish, clear snapshots immediately or keep last published values until republish overwrites?
