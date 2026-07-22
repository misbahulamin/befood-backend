## Why

Meal package prices are still entered manually at create time, while real costing now lives in month-based cycle finalize. Customers also only see thin meal fields (`total_price`, description) and cannot inspect the finalized menu/cost context needed to decide on a purchase. Connecting finalize → published meal price + public meal details closes that gap.

## What Changes

- **BREAKING** (admin meal create/update): stop requiring `total_price` on meal create; price becomes cycle-driven after finalize.
- On successful cycle plan **finalize**, update the linked `MealCategory.total_price` from finalized cycle totals (`snapshot_total_cost` / package price) and refresh derived per-meal display values.
- On **reopen**, keep the last published price until a new finalize (do not wipe customer-facing price mid-edit).
- Enrich **public** meal detail with the latest finalized cycle plan summary customers need: month/cycle size, package total, per-meal rate, and a clear food/servings breakdown (customer-safe; no admin-only margin internals unless useful as transparent pricing).
- Optionally hide or mark meals without any finalized price as not purchase-ready on public list (or show `null` price with `pricing_status`).
- Update docs/tests for create flow, finalize side-effect, and public detail contract.

## Capabilities

### New Capabilities

- `public-meal-offering`: Public meal list/detail that exposes purchase-ready pricing and finalized cycle meal details for customer decision-making.

### Modified Capabilities

- `meal-cycle-planning`: Finalize MUST publish pricing onto the linked meal package; reopen behavior clarified relative to published price.
- `meal-cycle-costing`: Finalized snapshots become the source of truth for the meal’s published package/total price (not suggestion-only).

## Impact

- **Models/APIs:** `MealCategory.total_price` nullability or equivalent pricing status; admin create serializer; public meal serializers/views.
- **Services:** `finalize_plan` gains publish step writing meal price from snapshots; public “current offering” resolver (latest finalized plan per meal).
- **Clients:** Admin meal forms drop required total price; customer apps read richer public detail to buy.
- **Docs:** Extend `meals/docs/backend/meal-cycle-management.md` + public meal API notes.
- **Orders:** Existing order flows that assume `total_price > 0` need guardrails when meal not yet priced.
