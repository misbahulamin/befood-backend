## 1. Data model

- [x] 1.1 Add `MealCategory.is_subscribable` boolean (default `false`); data-migrate Student/Regular/Premium (or current ongoing packages) to `true`
- [x] 1.2 Add `CustomerSubscription` (`PublicIdMixin`): customer, meal FK, name/period snapshots, `status` (`active`|`cancelled`), `started_on`, `cancelled_at`, `cancel_effective_on`, timestamps; unique constraint one active row per customer
- [x] 1.3 Add nullable `subscription` FK on `OrderDelivery`; allow nullable `order`; add unique `(subscription, service_date, meal_period)` for subscription-owned rows
- [x] 1.4 Register new models/fields in Django admin; create and apply migrations

## 2. Subscription domain services

- [x] 2.1 Implement subscribe service: validate plan (`is_active` + `is_subscribable`), one-active exclusivity, wallet gate (no debit), snapshots, `started_on` in meal-off timezone, atomic create
- [x] 2.2 Implement cancel service: set cancelled fields, skip `scheduled` slots with `service_date > cancel_effective_on`, leave today’s slots unchanged
- [x] 2.3 Implement `ensure_subscription_deliveries` rolling horizon (today through last day of next month); skip unpublished months; idempotent; do not generate after cancel
- [x] 2.4 Hook ensure into subscribe (same transaction) and add a management command for daily/cron plus post-menu-publish

## 3. Retire monthly customer order create

- [x] 3.1 Reject customer `POST` meal-order create with a stable subscribe-required error; create no `Order`
- [x] 3.2 Stop using month lock, future-month `year`/`month` create, and orderable-months as purchase gates
- [x] 3.3 Point current-package / my-active meal at the active `CustomerSubscription` (null when none); keep historical order list/detail read-only

## 4. Customer APIs

- [x] 4.1 `GET /api/v1/subscription-plans/` — verified customer catalog of active subscribable plans (lean payload, `public_id`)
- [x] 4.2 `POST /api/v1/subscriptions/` — subscribe by `plan_public_id`; `201`; OpenAPI + field errors (wallet, frozen, already subscribed, inactive plan)
- [x] 4.3 `GET /api/v1/subscriptions/current/` and `GET .../{public_id}/` — own subscription + read-only progress; `404`/`403` for others
- [x] 4.4 `POST /api/v1/subscriptions/current/cancel/` — owner cancel; object-level auth

## 5. Admin APIs

- [x] 5.1 Verified-admin CRUD for subscription plans under `/api/v1/web/subscription-plans/` writing `MealCategory` (`public_id`, name, period, thumbnail, description, `is_active`, `is_subscribable`)
- [x] 5.2 Admin paginated subscriptions list/detail under `/api/v1/web/subscriptions/` with filters `status`, plan `public_id`, date ranges; `400` on bad filters
- [x] 5.3 Reuse `OrderWalletSettings` GET/PATCH; document/apply `min_wallet_balance_to_order` as the subscribe minimum; customer wallet still exposes the value
- [x] 5.4 Extend mark-delivered / meal-off ownership so subscription-owned slots (null `order_id`) work; keep admin-only mark-delivered

## 6. Downstream ops

- [x] 6.1 Update meal-off/on ownership to the caller’s subscription deliveries; meal-off MUST NOT complete/cancel the subscription
- [x] 6.2 Update demand/kitchen statistics to count active-subscription deliveries (exclude cancelled subscription future slots); package grouping from subscription meal
- [x] 6.3 Update wallet payment context to reference subscription + delivery public ids; still no debit on subscribe or slot generation
- [x] 6.4 Scope `my-package-menu` to the active subscription plan; keep preview-without-subscription; empty packages when none

## 7. Data migration of in-flight orders

- [x] 7.1 RunPython: for each customer with a current non-cancelled order, create one active `CustomerSubscription` from the latest such order; attach remaining slots from today forward; skip customers who already have an active subscription
- [x] 7.2 Cancel extra future-month non-cancelled orders for those customers and skip their remaining scheduled slots

## 8. Tests

- [x] 8.1 Tests: subscribe success, snapshots, no `Order`, no wallet debit; reject inactive/non-subscribable plan, unverified, unauthenticated
- [x] 8.2 Tests: second active subscribe rejected; subscribe after cancel allowed; frozen wallet and below-minimum rejected; missing wallet as zero; already-subscribed error before wallet error
- [x] 8.3 Tests: rolling slot generation idempotent; unpublished month skipped without cancelling; end of month does not complete subscription; cancel skips future not today
- [x] 8.4 Tests: customer isolation; admin list filters and permission denials; legacy order create rejected; demand counts from subscription slots; meal-off ownership; delivered debit still works
- [x] 8.5 Tests: in-flight order migration creates one subscription and does not duplicate slots

## 9. Documentation

- [x] 9.1 Backend docs under `orders/docs/backend/` for subscription lifecycle, wallet gate, rolling slots, cancel rules, and retired order create
- [x] 9.2 Frontend docs: `orders/docs/frontend/customer-meal-subscription.md` and `orders/docs/frontend/admin-subscription-management.md` (endpoints, errors, Order Now migration)
- [x] 9.3 Update OpenAPI examples and related order/wallet frontend notes that still describe monthly repurchase
