## Why

BeFood’s bachelor-mess customers eat lunch and dinner year-round, but today’s product forces them to confirm a new meal package **every calendar month**. That monthly repurchase loop fights the business model: long-term mess service, not one-shot monthly checkout. Replacing repeated orders with a Netflix-style subscription lets a customer pick a plan once and keep receiving meals until they cancel.

## What Changes

- Introduce **subscription plans** (Student, Regular, Premium, and future plans) that verified admins create and manage from the admin panel, with enough configuration that new packages can be added without a code change.
- Introduce a **customer subscription** entitlement: a verified customer subscribes to one available plan; service continues for lunch/dinner according to that plan **until the customer cancels**.
- Reuse the existing **wallet eligibility gate** at subscribe time: check that the customer’s wallet is active and `balance >=` the admin-configured minimum (today `min_wallet_balance_to_order`). Passing the check MUST NOT debit the wallet.
- Generate **ongoing delivery slots** from the active subscription (rolling horizon), instead of creating a closed monthly `Order` with 60/62 slots that then completes.
- Keep per-meal operations that already work: meal-off/on, mark delivered, wallet debit on delivered slots, kitchen demand from those slots.
- **BREAKING:** Remove the customer **monthly/repeated order-create** flow (`POST` meal package order with `year`/`month`, month lock, orderable-months picker, and “order again next month”). Clients must subscribe instead of placing a new order each month.
- Historical completed/cancelled monthly orders remain readable for audit; they MUST NOT be the way new service is started.

## Capabilities

### New Capabilities

- `subscription-plan-catalog`: Verified-admin CRUD for subscription models (name, identity, meal period, active flag, and package configuration) so Student/Regular/Premium and future plans can be added without a deploy.
- `customer-meal-subscription`: Verified customer can subscribe to one available plan, see current subscription status, and cancel; service stays active until cancel.
- `subscription-wallet-eligibility`: Subscribe requires an active wallet with balance ≥ the admin-configured minimum; check only, no debit at subscribe time.
- `subscription-delivery-continuity`: While a subscription is active, the system keeps generating lunch/dinner delivery slots on a rolling horizon so the customer does not re-order each month.
- `admin-subscription-management`: Verified-admin list/detail/filter of customer subscriptions and operational delivery progress.
- `subscription-frontend-docs`: Frontend contracts for customer subscribe/cancel/status and admin plan + subscriber management.

### Modified Capabilities

- `order-lifecycle`: Customer purchase no longer creates a month-bounded order that activates and completes by quota; commercial entitlement is the subscription.
- `order-month-package-lock`: Same-month package exclusivity is replaced by **at most one active subscription per customer**.
- `order-wallet-min-balance`: Minimum-balance gate moves from meal-order create to subscribe.
- `order-wallet-min-balance-settings`: The admin singleton threshold is the amount required to **subscribe** (customers still read it for UX).
- `future-month-meal-ordering`: Customers no longer select `year`/`month` to place a package order.
- `orderable-meal-months`: The 13-month order-now picker is no longer the purchase path.
- `order-month-menu-publish-gate`: Subscribe MUST NOT require every future month’s menu to be published; unpublished months only block **slot generation / service for that month**.
- `order-delivery-tracking`: Expected slots come from an active subscription’s rolling window, not from a one-month order create.
- `period-aware-order-slots`: Lunch/dinner/both slot rules use the subscription plan’s meal-period snapshot.
- `customer-order-visibility`: “Current package” becomes the caller’s **current subscription** (plus historical monthly orders if still exposed as history).
- `admin-order-management`: Admin operations board is driven by active subscriptions and their deliveries, not monthly repurchase orders.
- `customer-meal-off`: Meal-off/on ownership is the customer’s subscription deliveries.
- `meal-demand-forecasting`: Kitchen counts come from non-cancelled **subscription** deliveries for the date/period.
- `meal-delivery-wallet-payment`: Delivered-slot wallet debit stays; payment context identifies the subscription (and delivery), not a monthly order purchase.
- `customer-meal-package-menu`: Full-month menu is scoped to the customer’s **subscribed plan**, not to a monthly order row.

## Impact

- **Orders app:** New subscription models/services/APIs; stop customer monthly `create_meal_order`; retarget delivery generation, meal-off, demand, and admin boards to subscriptions; keep `Order`/`OrderDelivery` history for past months.
- **Meals app:** Subscription plans reuse or wrap `MealCategory` (Student/Regular/Premium already exist as packages) so kitchen menu/cycle/pricing stay package-scoped.
- **Wallet:** Existing `OrderWalletSettings.min_wallet_balance_to_order` (or renamed equivalent) gates subscribe; per-delivery debit unchanged in timing (charge on `delivered` only).
- **Auth:** Verified customer for subscribe/cancel/status/meal-off; `IsVerifiedAdmin` for plan CRUD, settings, and subscriber ops.
- **Clients:** Customer app replaces Order Now / month picker with Subscribe + Cancel; admin panel gains subscription-plan management and subscriber list.
- **Docs/tests:** Backend + frontend docs, OpenAPI, and tests for subscribe, wallet gate, cancel, rolling slots, admin CRUD, and removal of monthly repurchase.
- **Non-goals:** Payment-gateway capture of a Netflix-style monthly invoice; auto-pause/cancel when wallet later drops below minimum (delivery debit already fails per slot); changing meal-cycle costing or menu-schedule authoring; daily/weekly one-shot POS checkout rewrite.
