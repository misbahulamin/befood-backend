## 1. Schema and shared cancel core



- [x] 1.1 Add additive nullable `cancelled_by` (FK to user) and `cancel_source` on `CustomerSubscription` with backward-safe migration

- [x] 1.2 Enhance `cancel_subscription` to classify each `SCHEDULED` delivery via `is_past_meal_cutoff`, soft-skip cancellable slots, preserve finalized/delivered/skipped, keep atomic + idempotent behavior

- [x] 1.3 Accept optional `cancelled_by`, `cancel_source`, and reason/note kwargs on the shared service; wire customer `cancel_current` to `cancel_source=customer`

- [x] 1.4 Add/adjust unit tests for lunch/dinner independent cutoff, exact boundary (`now == deadline` → skip), future skips, delivered untouched, repeat cancel idempotency (update `test_cancel_skips_future_not_today_*` expectations)



## 2. Finalized meal liability and withdrawable



- [x] 2.1 Add read-only helper to estimate a delivery charge from published slot `final_meal_price_snapshot` (reuse charge pricing source; no debit)

- [x] 2.2 Extend `compute_maximum_withdrawable` (and `Wallet.withdrawable_balance` / serializers) so active subscribers keep `recharge − meal_stop_threshold` and non-active use `recharge − finalized_meal_liability`

- [x] 2.3 Ensure `request_withdraw` uses the same helper under wallet lock; update wallet docs for cancelled-subscriber formula

- [x] 2.4 Add wallet tests: active threshold unchanged; post-cancel threshold off; liability retained; over-withdraw rejected; liability clears after charge



## 3. Admin cancel and preview APIs



- [x] 3.1 Implement `GET /api/v1/web/customers/{public_id}/cancel-subscription-preview/` on `AdminCustomerViewSet` (`IsVerifiedAdmin`), read-only classification + wallet figures

- [x] 3.2 Implement `POST /api/v1/web/customers/{public_id}/cancel-subscription/` calling canonical service with admin actor; support optional reason and Idempotency-Key if project pattern fits

- [x] 3.3 Add serializers + OpenAPI for preview/cancel request/response (cancelled_meals, preserved_finalized_meals, wallet block)

- [x] 3.4 Enrich activity payload refs with `cancel_source` / actor when present (reuse `build_activity_events`)

- [x] 3.5 API tests: verified admin success; unverified/non-admin denied; no active sub; preview read-only; preview vs cancel classification match; auth isolation



## 4. Backend docs



- [x] 4.1 Write `orders/docs/backend/` (or adjacent) admin subscription cancel workflow doc: endpoints, fields, cutoff rules, examples

- [x] 4.2 Update wallet customer/manual funding docs for post-cancel withdrawable formula



## 5. Frontend admin UX (`F:\befood\befood-frontend`)



- [x] 5.1 Add admin API client methods for cancel preview and cancel on `adminCustomerApi.ts`

- [x] 5.2 Add TanStack mutation hook with invalidation of customer detail, active subscription, subscriptions, meals, wallet overview, activity, and subscription caches

- [x] 5.3 Build `AdminCancelSubscriptionModal` on `AdminModal` showing backend preview + confirmation copy; pending/error/success via `sonner` + `getApiErrorMessage`

- [x] 5.4 Add Cancel Subscription control on `AdminCustomerDetailPage` Active Subscription for verified admin + active status only

- [x] 5.5 Add/adjust frontend tests or lightweight interaction coverage if the project pattern exists for admin modals/mutations



## 6. Verification and release



- [x] 6.1 Run targeted backend test suites (subscription cancel, meal cutoff, wallet withdrawable/funding, admin customer cancel)

- [ ] 6.2 Staging smoke: cancel before/after dinner cutoff; withdraw after cancel with preserved dinner; delivery board/kitchen counts for skipped vs preserved

- [ ] 6.3 Deploy backend (+ migration) before frontend; publish release note for customer self-cancel same-day semantic change

- [ ] 6.4 Confirm rollback path: remove/hide frontend button; revert backend deploy without un-skipping historical rows automatically

