# Optional ingredient per-serving cost (Frontend)

## What changed

`cost_per_customer` on ingredient create/update is **optional**. Admins may save a catalog row with only a name (and visibility/notes), then fill cost later.

Meaning of `cost_per_customer`: total cooking cost for **one customer serving or one piece**, depending how the product is used. It is **additive** with kg-derived cost — not an override. When both kg pricing and flat cost are set, line math uses both.

See the full additive formula guide: [`additive-ingredient-line-cost.md`](./additive-ingredient-line-cost.md).

## Ingredient form

| Field | Required | UI guidance |
| --- | --- | --- |
| `name` | yes | Text |
| `price_per_kg` + `customers_per_kg` | no (both or neither) | Kg pricing pair → drives `resolved_cost_per_customer` |
| `cost_per_customer` | no | Optional money input — “Cooking cost per customer / piece”. Allow empty. **Added** to kg unit when both set. |
| `pieces_per_kg` | no | Optional |
| `is_active` / `is_customer_visible` / `notes` | no | Unchanged |
| `product_role` | — | Not on this form (plan line only) |

### Create without cost

```json
{
  "name": "Unpriced Spice",
  "is_customer_visible": false
}
```

Response: `resolved_cost_per_customer` is `null`. Show “Cost unknown” (or hide the cost chip) — do not display `0`.

### Create with optional flat cost

```json
{
  "name": "Masala Cost",
  "cost_per_customer": "2.00",
  "is_customer_visible": false
}
```

Response: `resolved_cost_per_customer` is `null` (flat-only). Ready for plan attach via flat cost.

## Plan lines / summary

- Adding an unpriced ingredient (neither kg nor flat) to a plan line → `400` with `ingredient` message. Show toast / field error and link admin to edit the ingredient.
- `GET .../summary/` and `POST .../finalize/` also return `400` if any line ingredient later loses resolvable cost.
- Prefer filtering the ingredient picker with:

```text
has_cost = resolved_cost_per_customer != null || cost_per_customer != null
```

Do **not** require `resolved_cost_per_customer != null` alone (that blocks flat-only spices).

## Related

- Additive costing: [`additive-ingredient-line-cost.md`](./additive-ingredient-line-cost.md)
- Backend: [`../backend/meal-cycle-management.md`](../backend/meal-cycle-management.md) (§6 Ingredient, §4 Money formulas)
- Role/visibility form notes: [`plan-level-ingredient-role-visibility.md`](./plan-level-ingredient-role-visibility.md)
