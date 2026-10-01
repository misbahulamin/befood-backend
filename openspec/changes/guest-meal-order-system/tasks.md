## 1. Confirm open decisions & settings foundation

- [x] 1.1 Confirm open business decisions with product (cancellation/refund + quota restore; quota month = created_at vs service_date; meal-OFF + guest; recharge vs spendable floor; debit strategy; kitchen servings formula; per-request max qty; past dates; admin-on-behalf; notifications)
- [x] 1.2 Add `guest_meal_box_price` and `guest_meal_monthly_limit` to `OrderWalletSettings` with defaults `10.00` / `10` and migration
- [x] 1.3 Extend `orders/services/order_wallet_settings.py` + admin wallet-settings serializers/views/docs to read/update the new fields

## 2. Data model

- [x] 2.1 Add `GuestMealOrder` model (`PublicIdMixin`) with customer, subscription, service_date, meal_period, quantity, pricing snapshots, wallet_transaction FK, optional delivery FK, status, timestamps, indexes for monthly SUM queries
- [x] 2.2 Create migration and register admin read-only (or minimal) if project pattern requires

## 3. Domain services (no HTTP yet)

- [x] 3.1 Implement eligibility helpers reusing `get_active_subscription`, `periods_for_meal_period`, `resolve_published_slot_for_delivery`, `is_past_meal_cutoff`, `business_today`
- [x] 3.2 Implement pricing helper: base + box → unit/total with Decimal money quantize; reject when price missing
- [x] 3.3 Implement monthly usage SUM from guest records (Asia/Dhaka calendar month) and remaining capacity check
- [x] 3.4 Implement `preview_guest_meal` (read-only) and `create_guest_meal_order` atomic flow: lock → validate → debit_wallet → persist GuestMealOrder → link delivery
- [x] 3.5 Wire meal-stop floor validation per confirmed product formula; ensure create failure rolls back debit and debit failure skips create
- [x] 3.6 Support optional Idempotency-Key replay/conflict using wallet idempotency unique constraint pattern

## 4. Customer APIs

- [x] 4.1 Add serializers for usage, preview request/response, create request/response, list/detail (public_id only; no trusted client money fields)
- [x] 4.2 Add views: `GET usage`, `POST preview`, `POST create`, `GET list`, `GET detail`; mount under `/api/v1/`
- [x] 4.3 Map domain errors to existing project error shape / status codes (`422`/`409`/`404` as appropriate)
- [x] 4.4 Update OpenAPI/schema annotations for the new endpoints

## 5. Delivery, kitchen, and admin surfaces

- [x] 5.1 Aggregate and expose `guest_quantity` on deliveryman/admin today-board (or equivalent stop serializers)
- [x] 5.2 Update `orders/services/meal_demand.py` (and related APIs) so cooking/expected counts include countable guest units without double-charging on deliver
- [x] 5.3 Ensure `charge_delivered_meal` path remains unchanged for regular slot and never re-debits prepaid guest totals
- [x] 5.4 Add `guest_meal_ordered` to `build_activity_events` / confirmed event types in admin customer activity

## 6. Documentation

- [x] 6.1 Write `orders/docs/backend/guest-meal-order.md` (full workflow, endpoints, fields, errors, concurrency/idempotency)
- [x] 6.2 Write `orders/docs/frontend/guest-meal-order.md` (usage → preview → create client sequence)
- [x] 6.3 Update wallet threshold / customer subscription docs with cross-links where guest meal intersects meal-stop

## 7. Tests

- [x] 7.1 Unit/API: active subscriber success; no/cancelled subscription reject
- [x] 7.2 Pricing: base resolve, box add, multi-quantity total, missing price reject, snapshot stable after settings/slot price change
- [x] 7.3 Wallet: debit success; threshold reject; exact-threshold behavior per confirmed rule; debit fail ⇒ no guest row; guest persist fail ⇒ no debit
- [x] 7.4 Monthly quota: allow through 10; reject 11th; cumulative multi-order; prior month excluded; Asia/Dhaka month boundary
- [x] 7.5 Eligibility: invalid period/date; past cutoff; unsupported subscription period
- [x] 7.6 Concurrency: parallel creates cannot exceed monthly 10 or double-spend wallet
- [x] 7.7 Auth: cannot create for another customer; usage/remaining correct
- [x] 7.8 Integration: rider/board guest quantity visible; demand includes guest units; deliver does not re-charge guest
- [x] 7.9 Idempotency: same key replay; conflicting payload → 409

## 8. Verification gate

- [x] 8.1 Run focused guest-meal / demand / wallet-related test suites and fix failures
- [x] 8.2 Manual Swagger walkthrough: settings → usage → preview → create → board/demand/activity
- [x] 8.3 Confirm no application code paths hardcode box/meal prices outside settings defaults
