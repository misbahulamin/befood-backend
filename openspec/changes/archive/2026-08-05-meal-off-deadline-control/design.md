## Context

Customer meal-off is already live: `POST .../deliveries/{id}/meal-off` sets an owned `scheduled` delivery to `skipped` with `skip_source=customer` when business time is still at or before the period deadline from `MealOffSettings`. Delivery payloads expose `can_meal_off` and `meal_off_deadline_at`. Wallet payment already skips debit for `skipped` slots.

v1 explicitly deferred undo (“meal-on”). Product now requires customers to toggle Off ↔ On freely until the same lunch/dinner deadline, then freeze. Daily packages that meal-off their only slot may auto-complete via `complete_order_if_done`; meal-on must reopen that order so the restored slot can still be delivered.

Stakeholders: verified customers (mobile/web), kitchen/ops (today board still ignores `skipped`), verified admins (deadline settings unchanged).

## Goals / Non-Goals

**Goals:**

- Customer meal-on: customer-skipped → `scheduled` before the same deadline.
- Shared deadline lock: after deadline, neither Off nor On is allowed; status stays as-is.
- Eligibility on payloads: `can_meal_on` (and keep `can_meal_off` / `meal_off_deadline_at`).
- Reopen `completed` → `active` (or `confirmed` when appropriate) when meal-on restores a non-terminal slot.
- Preserve lunch/dinner deadline calendar math and admin settings singleton.
- Document default: no off = on = normal delivery + charge-on-delivered; off = no delivery expectation + no charge.

**Non-Goals:**

- Changing default clock values (still lunch previous-day `23:59`, dinner same-day `14:00`) unless admin configures them.
- Changing lunch/dinner calendar-day rules (lunch = `D−1` + time, dinner = `D` + time).
- Wallet credit/refund on meal-off; charging on meal-on itself.
- Admin-skip undo via this customer API (`skip_source=admin` stays admin-only).
- Bulk date-range Off/On.
- Allowing meal-on after deadline via customer self-service.

## Decisions

### 1. Same deadline for Off and On

Reuse `meal_off_deadline(service_date, meal_period)` and `meal_off_business_now()`. Eligible mutations require `now <= deadline` (inclusive, matching existing meal-off).

**Why:** One kitchen cutoff; product examples (Off then later On before 9 PM dinner / before lunch midnight cutoff) use one clock.

**Alternatives:** Separate on-deadline — rejected (ops complexity).

### 2. Meal-on restores to `scheduled` and clears customer skip metadata

`customer_meal_on(delivery, user)`:

1. Lock delivery + order.
2. Ownership + order not cancelled.
3. Status must be `skipped` and `skip_source` must be `customer` (reject admin skips).
4. Assert `now <= deadline`.
5. Set status `scheduled`; clear `skip_source`, `marked_by`, `marked_at` (or set `marked_*` to acting user/now for audit — prefer clear skip fields so board treats as normal scheduled; optional note append for history).
6. If order is `completed`, reopen to `active` (daily that never left `confirmed` → prefer `confirmed` if no delivered slots yet, else `active`) via an explicit internal transition helper.
7. Do not call wallet charge.

**Why:** Matches default “on = expect meal”; kitchen boards already list `scheduled`.

**Alternatives:** New status `meal_off` — rejected (reuse skipped). Soft flag without status change — rejected (boards/payment already keyed on status).

### 3. API: sibling meal-on action

```http
POST /api/v1/.../orders/{order_public_id}/deliveries/{delivery_public_id}/meal-on
```

Empty or optional `{ "note": "..." }` body. `200` + updated delivery. Errors: ownership `404`/`403`, wrong state `409`/`422`, past deadline `422` with clear message.

**Why:** Mirrors existing meal-off path; explicit Off/On is clearer for clients than a single toggle.

**Alternatives:** PATCH delivery status — rejected (customers must not arbitrary-status). Toggle endpoint — acceptable later; sibling POST is enough for v1.

### 4. Order reopen transition

Today `COMPLETED → *` is empty in `ALLOWED_TRANSITIONS`. Add a service-level `reopen_order_after_meal_on` that allows `completed → active` (and, if product prefers for never-started daily packages, `completed → confirmed`) with history note, used only from meal-on — not a general customer reopen API.

**Why:** Meal-off can complete the order; without reopen, meal-on cannot restore a deliverable slot.

**Alternatives:** Defer order completion until deadline passes — larger behavior change; reject for this change.

### 5. Eligibility helpers

- `can_meal_off`: unchanged (`scheduled`, not cancelled, before deadline).
- `can_meal_on`: `skipped` + `skip_source=customer` + not cancelled + before deadline.
- After deadline: both false; existing status unchanged.

### 6. Billing / delivery semantics (confirm only)

- `skipped` (customer off): not on cook board as expected meal; wallet MUST NOT debit (existing payment rules).
- Meal-on → `scheduled`: eligible for later `delivered` + debit; meal-on itself creates no wallet txn.
- Never-off slots remain `scheduled` by default generation — no customer action required.

## Risks / Trade-offs

- **[Risk] Reopening completed orders** → Mitigation: narrow helper + history note; reject if any concurrent admin mark; tests for daily single-slot Off→complete→On→active.
- **[Risk] Race: Off and On concurrent** → Mitigation: `select_for_update` on delivery.
- **[Risk] Customer undoes after kitchen already prepped (before deadline)** → Mitigation: product accepts deadline as the contract; ops still own admin mark.
- **[Trade-off] Admin skips not customer-undoable** → Intentional; admin path remains authoritative.
- **[Trade-off] Inclusive deadline** → Keep existing `<=` semantics; document in API docs.

## Migration Plan

1. Deploy meal-on service + endpoint + serializer fields + reopen helper.
2. No settings migration; existing `MealOffSettings` rows apply to On.
3. Rollback: hide/disable meal-on route; Off behavior remains.

## Open Questions

- Exact reopen target when meal-off completed a multi-slot order that had other terminal deliveries: default **`active`**.
- Whether to append an audit note on meal-on vs clearing all mark fields: default **clear skip_source/marked_*; optional note on delivery.note**.
