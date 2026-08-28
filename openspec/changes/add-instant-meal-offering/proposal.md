## Why

BeFood already serves subscribers from published monthly package menus (Student / Regular / Premium). Non-subscribers cannot yet browse those same cook-day meals as one-off “Instant Meals” with a separate, admin-controlled margin. We need a read-only Instant Meal display API and admin settings that reuse published menu slots without changing subscription pricing, publish flows, or production data.

## What Changes

- Add an isolated Instant Meal configuration (profit percent + display duration window) managed by verified admins.
- Expose a public/customer Instant Meal list API that projects **published** `MonthlyMenuSlot` rows into Instant Meal cards (one object per date × meal period × package), filtered by admin duration and excluding past dates.
- Compute Instant Meal price as: published slot **ingredient cost** + month **per-meal operational cost** + Instant **profit percent** on ingredient cost — without mutating subscription snapshots or package finalize logic.
- Return marketing fields (`subscriber_price`, numeric subscription hook value) so the frontend can show static subscribe messaging.
- Add backend and frontend integration documentation for Instant Meal display and admin settings.
- **No Instant Meal order/checkout** in this change (display + config only).
- **No BREAKING** changes to existing subscription meal packages, published menu calculation, slot snapshots, or existing APIs.

## Capabilities

### New Capabilities

- `instant-meal-offering`: Derive Instant Meal cards from published monthly menu slots (all active packages), apply date-window and past-date rules, compute Instant price, and expose a stable ordered list API for frontend display.
- `instant-meal-admin-settings`: Verified-admin singleton settings for Instant Meal `profit_percent` (default 50) and `duration_days` from the fixed allowlist `{1, 3, 7, 15, 25, 30}` (1 = Today).
- `instant-meal-frontend-docs`: Frontend-facing documentation covering Instant Meal list contract, admin settings contract, field meanings, ordering, and integration workflow (no order API yet).

### Modified Capabilities

- _(none)_ — Instant Meal is additive; existing `monthly-menu-schedule`, `meal-slot-final-price`, `meal-cycle-costing`, `customer-meal-package-menu`, and subscription specs keep their current requirements.

## Impact

- **App:** `meals` (settings model/migration if not already migrated, services, serializers, views, URLs, admin, tests, docs).
- **Reuse (read-only):** `MonthlyMenuSchedule` / `MonthlyMenuSlot` (published only), `MealCategory`, `OperationalCostMonth` via existing `resolve_per_meal_operational_cost`, existing unit-cost helpers — no changes to `finalize_plan`, `publish_schedule`, or slot snapshot write paths.
- **Permissions:** `IsVerifiedAdmin` for settings; Instant list intended for public/frontend display (align with existing public menu patterns).
- **Search:** `instant_meal` document type already exists in `search`; indexing Instant entities may be a follow-up once the list API is stable (out of scope unless explicitly tasked).
- **Out of scope:** Instant order placement, payment, delivery fulfillment, and any change to subscriber wallet debit logic.
