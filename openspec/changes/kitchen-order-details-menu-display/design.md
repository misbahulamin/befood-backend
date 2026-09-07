## Context

`GET /orders/kitchen/today-order-details/` builds a per-customer cooking list via `build_kitchen_order_details` in `orders/services/meal_demand.py`. Today each row exposes `name`, `phone`, `package_name`, and `address` only. Kitchen staff need the **published slot menu ingredients** for that customer’s package on `(service_date, meal_period)` — the same published `MonthlyMenuSlot` path already used by `get_ingredient_requirements` via `resolve_published_slot_for_delivery`.

The Admin SPA (`befood-frontend`) Order Details preview/print already prefers `menu_items_label` or joins `ingredient_names` / `menu_ingredients`, and falls back to `—` when those fields are absent. Chef print (`KitchenOrderSummaryPrintSheet`) should print package summary as **প্যাকেজ | চূড়ান্ত মিল** only; the on-screen Kitchen Today table may still show Expected / Meal off for operators.

## Goals / Non-Goals

**Goals:**

- Enrich each order-details customer row with today’s menu ingredient names and a joined display label (`mach + dhal + vat`).
- Avoid N+1 slot lookups when many customers share a package (cache by meal/package id).
- Keep existing fields (`package_name` included) so older clients do not break.
- Align Order Details UI/PDF with Menu column; keep Chef PDF package table lean (প্যাকেজ + চূড়ান্ত মিল); leave item-wise cooking section unchanged.
- Document and test the contract.

**Non-Goals:**

- Changing kitchen aggregate math, meal-off rules, or `today-meal-requirement` payload shape beyond print presentation.
- Removing `package_name` from the API in this change.
- Backend-generated PDF binaries or a new endpoint.
- Customer-facing menu APIs or inventory purchasing.

## Decisions

### 1. Resolve menu per package slot, not per delivery row from scratch

- **Choice:** For each delivery, resolve `meal_id` the same way demand does (`subscription.meal_id` coalesced with `order.meal_id`), then look up published slot ingredients once per distinct `meal_id` for the request’s `(service_date, meal_period)`.
- **Rationale:** Matches `get_ingredient_requirements` / kitchen kg math; one published menu per package-slot.
- **Alternatives considered:** Call resolve once per customer without cache (correct but wasteful); embed full ingredient objects with kg (too heavy for a customer sheet).

### 2. Response shape: additive fields

```json
{
  "name": "...",
  "phone": "...",
  "package_name": "Student Package",
  "address": "...",
  "ingredient_names": ["mach", "dhal", "vat"],
  "menu_items_label": "mach + dhal + vat"
}
```

- **Choice:** Always include `ingredient_names` (list of strings, sorted stably — prefer slot item order if available, else name sort) and `menu_items_label` (join with ` + `, or `""` / `null` when empty). Keep `package_name`.
- **Rationale:** Frontend already reads these keys; server-side label avoids client join drift.
- **Alternatives considered:** Replace `package_name` with menu label (**BREAKING**); only return label without list (harder to style later).

### 3. Missing / unpublished menu

- **Choice:** Empty `ingredient_names` and empty/null `menu_items_label`; still return the customer row. Do not set a top-level `ingredients_incomplete` on order-details (that remains on the requirement endpoint).
- **Rationale:** Order Details is a customer roster; incomplete menu should not drop people from the cook list.

### 4. Frontend split of concerns

- **Order Details:** Preview + print use Menu (ingredients); do not show Package as the primary food column.
- **Chef PDF:** Package summary headers/cells = প্যাকেজ + চূড়ান্ত মিল only. Item-wise section unchanged. Dashboard on-screen Expected / Meal off columns stay.
- **Rationale:** Matches kitchen handoff: cooks need final numbers on paper; ops still see expected/off on screen.

### 5. Implementation order

1. Backend service + serializer + OpenAPI + tests + docs.
2. Frontend verify/polish Order Details + Chef PDF + tests (sibling repo `befood-frontend`).

## Risks / Trade-offs

- **[Risk] Slot item order vs alphabetical** → Prefer published slot item order for kitchen familiarity; document in API docs.
- **[Risk] N+1 if cache forgotten** → Mandatory per-request dict cache keyed by `meal_id`.
- **[Risk] Ingredient display names change after publish** → Accept live resolution (same as kitchen requirement); snapshots are out of scope for order-details.
- **[Trade-off] Keeping `package_name`** → Slightly larger payload; avoids breaking any client still reading it.

## Migration Plan

1. Deploy backend first (additive fields).
2. Deploy / verify frontend that renders Menu from new fields (partially already present).
3. Rollback: clients ignore unknown fields; removing fields later would need a follow-up — not required for this ship.

## Open Questions

- None blocking — join separator is ` + ` (spaces around plus) to match product example `mach + dhal + vat`.
