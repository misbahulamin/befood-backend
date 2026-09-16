## Why

Admins viewing a published menu currently see only the subscriber selling price, but BeFood now serves two customer types with different profit rates: subscribers (cycle-plan `profit_percent`) and Instant/non-subscriber customers (`InstantMealSettings.profit_percent`). Without ingredient cost, dual selling prices, and profits on the published-menu admin API, operators cannot compare raw cost vs margin, and clients risk divergent frontend math. Centralizing the one-meal formula and returning both price ladders from the backend keeps admin UI, Instant cards, invoices, and future reports on one source of truth.

## What Changes

- Introduce a shared one-meal pricing helper (decimal money arithmetic) used by subscriber and Instant paths:  
  `profit = ingredient_cost × profit_percent / 100`,  
  `final_price = ingredient_cost + operational_cost + profit`.
- Enrich the admin published-menu detail payload (schedule/slots for `/admin/published-menus/{menu_id}` data) with additive cost and dual-pricing fields:
  - shared: `selected_ingredients_cost` / ingredient cost, `operational_cost`
  - `subscriber_pricing` (profit %, profit amount, final price) from plan profit + publish snapshots where applicable
  - `instant_pricing` (profit %, profit amount, final price) from latest active Instant meal settings
- Keep existing `price` / `final_meal_price` (subscriber) fields for backward compatibility; optionally mirror flat `subscriber_price` and `instant_price` for simple clients.
- Frontend MUST NOT recalculate prices; it only renders backend values (documented for the admin published-menu page).
- Do **not** change existing subscriber billing, wallet debit, or locked `final_meal_price_snapshot` semantics; Instant setting changes must not rewrite subscriber snapshots.
- Add/extend unit and API tests for shared calculation, dual fields on published menu detail, and Instant percent refresh behavior.
- Update backend (and frontend-facing) docs for the enriched contract.

## Capabilities

### New Capabilities

- `published-menu-dual-pricing`: Admin published-menu detail exposes per-slot/meal ingredient cost, operational cost, subscriber pricing ladder, and Instant pricing ladder from backend calculations (additive, non-breaking fields).

### Modified Capabilities

- `meal-cycle-costing`: One-meal price preview formula becomes an explicit reusable shared calculation contract (same math for subscriber plan profit % and Instant settings profit %).
- `monthly-menu-schedule`: Admin full schedule/detail responses MUST include dual-pricing fields alongside existing subscriber final meal price.
- `meal-slot-final-price`: Clarify that published subscriber snapshots remain authoritative for subscription charging; Instant prices on admin views are derived live from Instant settings + cost inputs and MUST NOT mutate slot subscriber snapshots.

## Impact

- **Services:** Prefer consolidating/wrapping `build_one_meal_price_preview` (and Instant slot pricing) behind a shared `calculate_meal_price` (e.g. `meals/services/pricing.py` or equivalent); wire Instant settings load into published-menu serialization.
- **APIs:** Admin published menu / monthly menu schedule detail serializers and OpenAPI schemas; existing Instant list already uses Instant profit — keep formulas aligned.
- **Models:** No required schema change if slot already stores ingredient/operational/profit snapshots; Instant profit continues to come from `InstantMealSettings`.
- **Safety:** Subscriber `price` / `final_meal_price_snapshot` and delivery wallet debit paths unchanged; additive response fields only.
- **Clients:** Admin published-menus UI shows table/detail of cost + dual prices/profits; Instant settings change reflected on refresh without republishing for Instant ladder.
- **Docs/tests:** `meals` backend docs + tests for pricing helper, schedule detail, Instant percent change.
