## Why

Customers can only place a meal package for the server’s “today”-derived month. They cannot choose an upcoming meal month in advance, and order creation does not verify that the admin has published that month’s menu. Subscriptions need advance ordering for published future months while keeping per-month package lock and wallet minimum eligibility.

## What Changes

- Allow verified customers to select a **meal month** when placing an order: **current calendar month through the next 12 months** (13 selectable months total). Default selection is the current month.
- Persist the selected meal month on the order via the existing `order_month` (`YYYY-MM`) field; compute `order_start_date` / `order_end_date` / deliveries for that target month (not only “today”).
- Gate order confirmation (and order-time menu preview) on a **published** `MonthlyMenuSchedule` for the selected year-month and meal category. If not published, reject with a clear bilingual-friendly message (e.g. “This month's menu has not been published yet…”).
- Expose a customer API to list orderable months with publish status so clients can render the month picker without guessing.
- Keep existing eligibility integrated **per selected meal month**:
  - at most one non-cancelled package per `(customer, order_month)` (month lock);
  - wallet balance ≥ admin `min_wallet_balance_to_order` (eligibility only; no debit).
- Update OpenAPI, tests, and frontend/backend docs (including a frontend integration guide after implementation).

## Capabilities

### New Capabilities
- `future-month-meal-ordering`: Customer selects a target meal month (current … +12 months) on order create; server validates the window, sets `order_month` and service period for that month, and creates the package order.
- `orderable-meal-months`: Customer-facing list of selectable meal months with published-menu status (and enough metadata for the month picker + empty-state message).
- `order-month-menu-publish-gate`: Order create (and pre-order menu preview for a month) requires a published monthly menu schedule for the selected meal + year-month; unpublished months return a clear, operator-safe message.

### Modified Capabilities
- `customer-meal-package-menu`: Support reading a published monthly menu for a selected year-month during the order flow (preview before an order exists for that month), not only after a package order is already placed.

## Impact

- **Orders:** `OrderCreateSerializer` / `create_meal_order` / `calculate_order_period` (target-month aware); OpenAPI; tests; docs under `orders/docs/`.
- **Meals:** Reuse `published_schedule_for_meal` / `MonthlyMenuSchedule`; optional pre-order menu preview endpoint or query extension; docs under `meals/docs/frontend/`.
- **Eligibility:** Reuse `check_existing_monthly_lock` and `check_wallet_min_balance` against the **selected** `order_month` (no change to wallet debit or admin settings model).
- **Clients:** Mobile/web order confirm UI adds month picker (default = current month), handles unpublished-month messaging, and sends selected month on create.
- **Out of scope:** Past months, wallet payment debit, changing admin publish workflow, multi-package same month.
