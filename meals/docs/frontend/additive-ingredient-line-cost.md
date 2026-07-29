# Additive ingredient line cost (Frontend)

## What changed

Meal-cycle **line product cost** no longer uses a single exclusive unit cost (kg **or** flat).

**New formula (server is source of truth):**

```text
line_product_cost = (resolved_cost_per_customer + cost_per_customer) × servings_count
product_cost      = sum(line_product_cost)   // unchanged rollup
```

| Symbol | Meaning |
| --- | --- |
| `resolved_cost_per_customer` | **Kg-only** unit: `price_per_kg ÷ customers_per_kg`. `null` if no complete kg pair. |
| `cost_per_customer` | Stored **flat** cooking / piece cost for one customer or one piece. May be `null`. |
| Missing side in the sum | Treat as `0` when the other side exists. |
| Both missing | Ingredient is unpriced — cannot attach to a plan line; summary/finalize return `400`. |

**BREAKING for UI assumptions:** If kg pricing exists, the API no longer ignores flat `cost_per_customer`. Both add. Do not copy historical “resolved replaces flat” copy into labels.

Target client: **web admin** (meal cycle + ingredient catalog). Public meal detail still omits internal costing bands.

## Field dictionary (ingredient)

| Field | Writable | Display |
| --- | --- | --- |
| `price_per_kg` + `customers_per_kg` | yes (both or neither) | Material / kg pricing |
| `cost_per_customer` | yes, optional | “Cooking cost per customer / piece” — **additive**, not an override of kg |
| `resolved_cost_per_customer` | read-only | Show only when not `null`. Label as “From kg” / material unit. Never show `0` for `null`. |

### Resolvable for plan attach?

Show “ready for plan” when **either** kg pair is complete **or** flat `cost_per_customer` is set (or both). Prefer:

```text
has_cost = resolved_cost_per_customer != null || cost_per_customer != null
```

Do **not** require `resolved_cost_per_customer != null` alone (that would block flat-only spices).

## Ingredient form UI

1. Keep kg pair inputs and optional flat cost input.
2. Optional live preview chip (client-side, Decimal-safe or defer to server):

```text
unit preview = (resolved ?? 0) + (flat ?? 0)
```

3. Help text example: “Flat cooking cost is **added** to kg-derived cost when both are set.”
4. Warn admins not to paste the same kg-derived number into flat (would double-count).

### Example responses

**Kg only**

```json
{
  "name": "Beef",
  "price_per_kg": "650.00",
  "customers_per_kg": "12.00",
  "cost_per_customer": null,
  "resolved_cost_per_customer": "54.166667"
}
```

Unit for costing: `54.166667 + 0`.

**Flat only**

```json
{
  "name": "Masala",
  "price_per_kg": null,
  "customers_per_kg": null,
  "cost_per_customer": "2.000000",
  "resolved_cost_per_customer": null
}
```

Unit for costing: `0 + 2.00`. Show “From kg: —” and “Cooking: 2.00”.

**Both (additive)**

```json
{
  "name": "Chicken",
  "price_per_kg": "650.00",
  "customers_per_kg": "12.00",
  "cost_per_customer": "2.000000",
  "resolved_cost_per_customer": "54.166667"
}
```

Unit for costing: `54.166667 + 2.00 = 56.166667`.  
If `servings_count = 10` → `line_product_cost ≈ 561.67` (server quantization wins).

## Plan lines / summary / finalize

1. Ingredient picker: allow rows with `has_cost` (see above); block or warn on fully unpriced.
2. On attach error (`400` + `ingredient`): toast + link to edit ingredient pricing.
3. Summary table columns (recommended):

| Column | Source |
| --- | --- |
| Ingredient | `ingredient_name` |
| Role | `product_role` |
| Servings | `servings_count` |
| From kg | `resolved_cost_per_customer` (or line-detail equivalent) |
| Cooking | flat `cost_per_customer` |
| Line cost | `line_product_cost` (**trust server**) |
| Est. kg | `estimated_kg` if present |

4. Package totals: keep using server `product_cost`, `other_cost`, `profit`, `total_cost`, `per_meal_rate`. Do not re-implement rollup in the browser except for optimistic preview; always refresh from `GET .../summary/` after line edits.
5. After this backend ships, reopen + re-summary any draft plan whose ingredients have **both** costs — numbers will rise vs old exclusive math. Finalized snapshots stay frozen until reopen + recalculate.

## Auth / headers

Unchanged: verified admin JWT; same meal-cycle and ingredient endpoints as today (`X-Client-Type: web` when used).

## Edge cases

| Situation | UI |
| --- | --- |
| `resolved_cost_per_customer` is `null` | Do not show `0`; show “—” / “No kg pricing” |
| Flat empty, kg present | Cooking column “—”; line cost from kg only |
| Kg empty, flat present | From-kg “—”; line cost from flat only |
| Both empty | Disable add-to-plan; “Cost unknown” |
| Incomplete kg pair on save | Show field error (both required together) |

## Related

- Backend formulas: [`../backend/meal-cycle-management.md`](../backend/meal-cycle-management.md) (§ money formulas)
- Optional catalog pricing: [`ingredient-per-serving-cost.md`](./ingredient-per-serving-cost.md)
- OpenSpec change: `additive-ingredient-line-cost`
