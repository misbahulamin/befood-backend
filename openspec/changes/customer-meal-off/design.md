## Context

Orders already generate per-slot `OrderDelivery` rows (`service_date` + `meal_period` lunch/dinner). Admins can mark `delivered` / `skipped`. Customers can only cancel whole orders early — they cannot opt out of a single meal before kitchen prep.

Real bachelor-home ops: cook (buwa) prepares lunch the next morning, so lunch for day D must be meal-off by end of day D−1; dinner for day D must be meal-off by afternoon of day D. Defaults: lunch cutoff **23:59 previous day**, dinner cutoff **14:00 same day**. Times must be admin-configurable in a business timezone (default `Asia/Dhaka`), similar to `MenuRevealSettings`.

Stakeholders: verified customers (mobile/web), verified admins (settings + kitchen boards).

## Goals / Non-Goals

**Goals:**

- Customer meal-off for an owned `scheduled` delivery slot before the configured deadline.
- Persist slot as no-meal for that user (reuse `skipped` status with clear customer source).
- Admin GET/PATCH meal-off deadline settings (lunch previous-day time, dinner same-day time, timezone).
- Expose eligibility helpers on delivery representations (`can_meal_off`, `meal_off_deadline_at`).
- Keep admin `mark` unrestricted by customer deadlines.

**Non-Goals:**

- Refunds, wallet credit, or package price adjustment for meal-offs.
- Undoing meal-off after the deadline (optional “turn meal back on” only if still before deadline — see open questions; default: no undo in v1).
- Bulk meal-off for a date range in v1 (single slot per request).
- Changing menu reveal times or cook staffing schedules.
- Auto meal-off for cancelled orders (already handled by order cancel / lifecycle).

## Decisions

### 1. Reuse `OrderDelivery.status = skipped` with `skip_source`

Add `skip_source` (`customer` | `admin` | null) and set `marked_by` / `marked_at` on customer meal-off (`marked_by` = requesting user). Kitchen/today-board already treat `skipped` as non-cook.

**Why:** Avoid a parallel status enum; ops already understand skipped.

**Alternatives:** New status `meal_off` — rejected (breaks lifecycle terminal set). Soft-delete slot — rejected (progress counts need a row).

### 2. Separate `MealOffSettings` singleton (not MenuRevealSettings)

Fields:

- `timezone` (IANA, default `Asia/Dhaka`)
- `lunch_off_time` — time-of-day on **previous** calendar day (default `23:59:00`)
- `dinner_off_time` — time-of-day on **service** calendar day (default `14:00:00`)

Deadline computation:

- Lunch on date `D`: deadline = `(D - 1 day)` at `lunch_off_time` in settings timezone  
- Dinner on date `D`: deadline = `D` at `dinner_off_time` in settings timezone  

Eligible iff `business_now() <= deadline` (inclusive of the deadline instant).

**Why:** Reveal (when menu becomes visible) ≠ opt-out cutoff; keep models/APIs separate.

### 3. API shape

Customer (owner only):

```http
POST /orders/{order_id}/deliveries/{delivery_id}/meal-off
```

Optional body: `{ "note": "..." }`. Success `200` returns updated delivery (+ order progress fields if useful).

Admin settings:

```http
GET/PATCH /api/v1/web/.../meal-off-settings
```

(or under `/orders/` web namespace to match admin order ops — place beside existing admin order routes).

### 4. Service layer

`customer_meal_off(delivery, user, note="")` in `orders/services/`:

1. `select_for_update` delivery + order  
2. Assert order.customer == user.customer profile  
3. Assert order not cancelled  
4. Assert status == scheduled  
5. Assert now ≤ deadline for `(service_date, meal_period)`  
6. Set status skipped, skip_source=customer, marked_by, marked_at, note  
7. `complete_order_if_done` if all slots terminal  

Do **not** route customer calls through admin `mark_delivery` permission path.

### 5. Serializer enrichment

On delivery nested serializers (customer detail / current package):

- `can_meal_off`: bool  
- `meal_off_deadline_at`: RFC3339 UTC (or local Z)  
- `skip_source`: when skipped  

### 6. Daily packages

Same rules apply: if the package has a lunch and/or dinner slot, meal-off is allowed until that slot’s deadline. Completing via meal-off still closes the order when all expected slots are terminal.

## Risks / Trade-offs

- **[Risk] Clock / timezone mistakes** → Mitigation: one `business_now()` helper using settings timezone; tests with frozen clocks.
- **[Risk] Customer meal-off confused with admin skip** → Mitigation: `skip_source` + docs; board can filter.
- **[Risk] Inclusive 23:59 vs “before midnight”** → Mitigation: document inclusive deadline; store TimeField to the second (23:59:00).
- **[Trade-off] No refund** → Product accepts operational skip only for v1.
- **[Trade-off] No undo** → Simpler kitchen planning; reopen only via admin if needed later.

## Migration Plan

1. Add `MealOffSettings` + seed defaults; add `OrderDelivery.skip_source` nullable.  
2. Deploy APIs.  
3. Rollback: hide customer endpoint; settings row harmless.

## Open Questions

- Allow undo meal-off (back to `scheduled`) while still before deadline? **Default v1: no.**  
- Should meal-off be allowed on `confirmed` orders before start date for future slots? **Yes**, if slot exists and deadline not passed.  
- Web-only settings vs shared admin path — follow existing admin order URL conventions.
