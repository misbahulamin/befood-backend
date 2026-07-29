# Plan-level ingredient role & customer visibility (Frontend)

## What changed

1. **Do not send `product_role` on ingredient create/update.** Catalog fields: pricing, `is_active`, `is_customer_visible`, `notes`.
2. **Set `product_role` when editing cycle plan lines** (bulk matrix or single line create). Required.
3. **Customer menus** (`today-menu`, `my-package-menu`) and public meal `menu_items` hide ingredients with `is_customer_visible=false`. Roles shown are from the package plan line.
4. **Admin schedule UI** still shows all assigned ingredients (including hidden costing items).

## Ingredient form

| Field | Required | UI |
| --- | --- | --- |
| name | yes | Text |
| pricing (`price_per_kg`/`customers_per_kg` or `cost_per_customer`) | no | Optional; both kg fields or neither. Flat cost = per customer/piece. Empty allowed. |
| `is_active` | no | Toggle |
| `is_customer_visible` | no | Toggle (default on). Label e.g. “Show on customer menu” |
| `product_role` | — | **Removed** from this form |

Example create (with optional cost):

```json
{
  "name": "Masala Cost",
  "cost_per_customer": "2.00",
  "is_customer_visible": false
}
```

Example create (no pricing yet):

```json
{
  "name": "Unpriced Spice",
  "is_customer_visible": false
}
```

Plan lines reject unpriced ingredients (`400` on `ingredient`). See [`ingredient-per-serving-cost.md`](./ingredient-per-serving-cost.md).

## Plan lines matrix

Each row needs role for **this package/month**:

```json
{
  "lines": [
    { "ingredient": 1, "servings_count": 60, "product_role": "main" },
    { "ingredient": 4, "servings_count": 60, "product_role": "side" },
    { "ingredient": 5, "servings_count": 60, "product_role": "staple" }
  ]
}
```

Missing `product_role` → `400`. Same vegetable can be `main` on Package A and `side` on Package D.

## Customer package / today menu

- `ingredients[].product_role` comes from the plan, not the catalog.
- Hidden ingredients never appear in the list (no need for client-side filter).

## Filters

| Endpoint | Filters |
| --- | --- |
| `/meals/ingredients/` | `is_active`, `is_customer_visible`, `search` (no `product_role`) |
| `/meals/cycle-plan-lines/` | `plan`, `ingredient`, `product_role` |

## Related

- Backend: [`../backend/plan-level-ingredient-role-visibility.md`](../backend/plan-level-ingredient-role-visibility.md)
- Customer menu contract: [`customer-package-menu.md`](./customer-package-menu.md)
