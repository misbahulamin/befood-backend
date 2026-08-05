## Why

Customers can already create a meal package order, but the system does not yet run a complete post-purchase lifecycle: admins cannot reliably list and filter successful orders for operations, and there is no delivery tracking that closes daily packages after one delivery or drives monthly packages through two meal periods per day (60/62 slots per month). Without this, kitchen and admin cannot operate active vs inactive packages against the current month calendar.

## What Changes

- Complete the **customer → order → delivery → completion** workflow so a successfully placed order is visible to admin and progresses through lifecycle statuses.
- Add **admin order list/detail APIs** with filters: meal type (`daily` / `weekly` / `half_monthly` / `monthly`), order status (active / inactive / completed / cancelled / etc.), `order_month`, and date range.
- Introduce **delivery slots** bound to each order: `lunch` / `dinner` (or a single slot for daily one-shot packages), with mark-delivered / skip semantics.
- Enforce **daily package rules**: one delivery total; after that delivery the order becomes `completed` (inactive for further delivery).
- Enforce **monthly package rules**: up to **2 deliveries per calendar day** within the order window; expected total deliveries = calendar days × 2 (**60 or 62** for 30-/31-day months), aligned with existing `total_meals_for_month`.
- Clarify **weekly / half-monthly** active windows: service days start from purchase (or start date) and remain active only on days inside the order period; admin filters can show which packages are active for “this month’s days.”
- Auto-transition `confirmed` → `active` when the order start date is reached (or on first eligible delivery day), and `active` → `completed` when all expected deliveries are done or the end date passes with no remaining slots.
- Ship beginner-friendly backend documentation for the full order + delivery workflow.

No **BREAKING** change to the existing customer create / my-orders / cancel / current-package contracts (additive fields and new admin + delivery endpoints only).

## Capabilities

### New Capabilities

- `order-lifecycle`: Full status lifecycle for meal package orders (`pending` → `confirmed` → `active` → `completed` / `cancelled`), including activation and completion rules by meal type.
- `order-delivery-tracking`: Per-order delivery slots (date + meal period), expected counts by package type, mark-delivered/skip, and auto-close when daily one-shot or monthly quota is fulfilled.
- `admin-order-management`: Admin-only paginated order list/detail with filters (meal type, status/active-inactive, month, date range) and delivery progress summary.
- `customer-order-visibility`: Customer can see own successful orders, current active package, and delivery progress without seeing other customers’ data.

### Modified Capabilities

- (none — no existing `openspec/specs/` capability covers order purchase/admin; meal-cycle and menu-schedule specs stay unchanged at requirement level)

## Impact

- **App:** `orders/` (models for delivery slots, services for lifecycle + delivery, filters, admin + customer APIs, tests, docs under `orders/docs/backend/`).
- **Related reads:** `meals/` package type and `total_meals_for_month` / cycle totals for expected delivery counts; optional link to menu schedule meal periods (`lunch`/`dinner`).
- **Auth:** verified customer for place/view own orders; admin (`IsVerifiedAdmin` / group permission) for management list/filter/mark-delivered.
- **Clients:** customer mobile/web (order create + progress); admin web (order board + filters + delivery marking).
- **Non-goals for this change:** payment gateway settlement, courier GPS routing, inventory deduction, cart multi-item checkout rewrite, changing meal cycle costing formulas.
