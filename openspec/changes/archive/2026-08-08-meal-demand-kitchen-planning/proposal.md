## Why

Customers on monthly (and other) meal packages often meal-off individual lunch/dinner slots, so kitchen headcount is not the same as active subscriber count. Without a demand view tied to meal-off deadlines, Admin and Kitchen cannot reliably know how many meals to cook or how much ingredient to prep, which drives overcooking and food waste. Meal-off and delivery slots already exist; this change turns that operational signal into real-time expected/final counts, package-wise breakdowns, ingredient requirements, and durable history for analysis.

## What Changes

- Add **meal demand forecasting** that computes, per `service_date` + `meal_period` (+ package):
  - **Expected meal count** from active order deliveries that include that slot (package / subscription aware)
  - **Meal-off count** from customer/admin skipped deliveries for that slot
  - **Final cooking count** = Expected − Meal Off
  - **Confirmation status**: `estimated` while the slot’s meal-off deadline has not passed; `confirmed` after the deadline
- Expose **Admin analytics APIs** with date, package, and lunch/dinner filters returning overall metrics, package-wise breakdown, and optional meal-off detail
- Expose a **lean Kitchen “today requirement” API** that defaults to today’s date and the current meal period (lunch vs dinner by business clock) and returns cooking headcount plus aggregated ingredient quantities
- Compute **ingredient quantities** from the published monthly menu / cycle plan ingredients for that date+period and package, scaled by final cooking count (using catalog kg yield where available)
- **Persist historical snapshots** (date, meal time, package, expected, off, final, ingredient requirement, timestamps, confirmation status) after deadline confirmation and/or on a controlled refresh path for later food-cost and demand analysis
- Add a **Historical report API** for prior dates (final cooking counts, meal-off analysis)
- No **BREAKING** changes to existing customer meal-off, wallet, or order APIs; this is additive admin/kitchen tooling that reads existing delivery + menu data

## Capabilities

### New Capabilities

- `meal-demand-forecasting`: Compute and expose expected / meal-off / final cooking counts with estimated-vs-confirmed semantics, overall and package-wise, filtered by date and meal period for Admin analytics
- `kitchen-cooking-requirement`: Lean Kitchen/Admin API for today’s (or explicit) cooking headcount and automatic ingredient quantity aggregation for the active meal period
- `meal-demand-history`: Persist and query historical demand snapshots (counts + ingredient requirements) for business, cost, and demand analysis

### Modified Capabilities

- (none) — existing `customer-meal-off`, `meal-off-deadline-settings`, `period-aware-order-slots`, `monthly-menu-schedule`, and ingredient catalog requirements remain the source of truth; this change consumes them without changing their contracts

## Impact

- **Apps**: primarily `orders` (delivery/meal-off aggregates), `meals` (package, cycle plan, monthly menu slot ingredients, ingredient catalog), possibly a thin new module or `orders`/`meals` services for demand snapshots
- **APIs** (web/admin + kitchen; exact paths finalized in design, aligned to `/api/v1/web/...` conventions):
  - Admin meal statistics (date / package / period filters)
  - Kitchen today cooking requirement (minimal payload)
  - Admin meal demand history / reports
- **Data**: new historical snapshot model(s); reads `OrderDelivery`, meal-off settings timezone/deadlines, published menu schedule lines, ingredient kg yield (`customers_per_kg` → kg per customer)
- **Permissions**: verified admin / kitchen-staff groups only; customers must not access demand or kitchen requirement endpoints
- **Dependencies**: meal-off deadline settings; order delivery statuses; package meal period; monthly menu schedule publish state for ingredient lines
- **Docs/tests**: backend + frontend docs under app docs; API tests for counts, confirmation status, filters, kitchen default period, history persistence, and authorization
