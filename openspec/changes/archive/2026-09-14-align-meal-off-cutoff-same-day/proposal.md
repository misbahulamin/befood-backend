## Why

The Admin Panel already lets operators set lunch/dinner meal ON/OFF cut-off times, and the frontend applies product rules correctly: lunch for service date `D` locks after midnight on `D`, and dinner for `D` locks after the afternoon cut-off on `D`. The backend still uses an older calendar rule (lunch = `D−1` + time, defaults `23:59` / `14:00`), so `can_meal_off` / `can_meal_on`, mutation rejection, and `meal_off_deadline_at` disagree with the frontend and with kitchen confirmation timing.

## What Changes

- **BREAKING** (behavior): Lunch meal-off/on deadline becomes **same calendar day as the lunch service date** at `lunch_off_time`, not the previous day.
- **BREAKING** (defaults): Default cut-offs become lunch `00:00:00` and dinner `16:00:00` (Asia/Dhaka), matching product examples (lock after ~12:01 AM for lunch, after ~4:01 PM for dinner).
- Keep a single shared deadline that gates **both** customer meal-off and meal-on.
- Keep admin GET/PATCH meal-off settings as the source of truth; updated times apply immediately to eligibility and deadline payloads.
- Align kitchen/demand confirmation status and docs/tests with the same deadline helper (no separate cut-off math).
- Data migration: update model field defaults and existing singleton row values when they still hold the old defaults (do not overwrite custom admin times that already differ).

## Capabilities

### New Capabilities

<!-- None — this aligns existing meal-off deadline behavior. -->

### Modified Capabilities

- `meal-off-deadline-settings`: Same-day lunch deadline math; new default lunch/dinner times; admin update still applies to Off and On.
- `customer-meal-off`: Meal-off and meal-on enforcement scenarios and deadline wording for lunch/dinner under the new calendar + defaults.
- `meal-demand-forecasting`: Confirmation status must reuse the updated meal-off deadline rules (no prior-day lunch wording).

## Impact

- `orders/services/meal_off.py` (`meal_off_deadline`)
- `orders/models.py` (`MealOffSettings` defaults/help text) + migration
- Serializers/OpenAPI copy that document previous-day lunch / old defaults
- `orders/tests/test_customer_meal_off.py`, `orders/tests/test_meal_demand.py` (and any other deadline assertions)
- Docs: `orders/docs/backend/customer-meal-off.md`, frontend meal-off / kitchen planning docs, auto-meal-delivery notes that cite old defaults
- Consumers of `meal_off_deadline` (meal demand confirmation, kitchen default slot inference still uses `dinner_off_time` clock only — verify after default moves to 16:00)
- Frontend Admin Panel already correct; backend becomes the matching source of truth via settings + deadline helper
