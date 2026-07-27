## Why

Customers already purchase a meal package for a month, and operators already publish a full monthly lunch/dinner menu per package — but the only customer-facing menu API today is `GET /meals/today-menu/`, which reveals only the current day's visible periods. Customers need a way to see the full published monthly menu for the meal package they own, so they can plan meals ahead.

## What Changes

- Add a customer-facing API that returns the **full published monthly menu** (all lunch/dinner slots for the month) for the authenticated customer's active meal package(s).
- Resolve the menu from the customer's current/active order → meal package → published `MonthlyMenuSchedule` for the relevant cycle month.
- Return day-by-day lunch and dinner items (ingredients) in a lean customer payload — not the admin schedule CRUD shape.
- Keep existing `today-menu` behavior unchanged (reveal-time gating stays for "today only").
- Add tests covering auth, ownership/package resolution, published vs unpublished schedules, and empty/missing menu cases.
- Add backend (and frontend-facing) documentation for the new endpoint.

## Capabilities

### New Capabilities
- `customer-meal-package-menu`: Authenticated verified customer can retrieve the full published monthly lunch/dinner menu for their active meal package(s).

### Modified Capabilities
- (none)

## Impact

- **APIs:** New customer endpoint under `/meals/` (alongside existing `today-menu`), using `IsVerifiedCustomer`.
- **Services:** New or extended service in `meals/services/` that builds the monthly menu payload from published `MonthlyMenuSchedule` + slots/items, keyed off the customer's active order(s).
- **Models:** No schema change expected — reuses `Order`, `MealCategory`, `MealCycle`, `MonthlyMenuSchedule`, `MonthlyMenuSlot`, `MonthlyMenuSlotItem`.
- **Clients:** Mobile/web customer apps can show the full month calendar menu after login.
- **Docs/tests:** New coverage and docs under `meals/docs/` and `meals/tests/`.
