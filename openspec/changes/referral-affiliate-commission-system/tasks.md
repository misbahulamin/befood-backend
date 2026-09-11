## 1. Foundations & settings

- [x] 1.1 Create Django app `referrals` with standard layout (`models`, `services/`, `api/`, `admin`, `tests/`, `docs/`) and register in `INSTALLED_APPS`
- [x] 1.2 Add settings: `REFERRAL_ENABLED`, `REFERRAL_COMMISSION_PERCENT` (default `5`), `REFERRAL_LINK_BASE_URL`, validate rate-limit settings, and document in base settings
- [x] 1.3 Add Admin Wallet transaction types for referral commission expense and reversal (not customer-funding custody types)

## 2. Wallet dual-bucket migration & consistency (HIGH)

- [x] 2.1 Add `recharge_balance` and `commission_balance` to `Wallet`; data-migrate `recharge_balance = balance`, `commission_balance = 0`
- [x] 2.2 Validate every wallet `balance == recharge_balance + commission_balance` in migration; fail migration on drift
- [x] 2.3 Add management command `verify_wallet_balance_consistency` (non-zero exit on invariant violations)
- [x] 2.4 Add `recharge_balance_after` and `commission_balance_after` on `WalletTransaction`; enforce `balance_after == sum` on completed rows
- [x] 2.5 Extend `WalletTransaction.Type` with `referral_commission` and `referral_commission_reversal`
- [x] 2.6 Update `wallet.services.ledger` for bucket-aware credit/debit + after snapshots under `select_for_update`
- [x] 2.7 Update meal payment debit path to consume `commission_balance` before `recharge_balance`
- [x] 2.8 Update `request_withdraw` / reject-restore to use only `recharge_balance`
- [x] 2.9 Update recharge approve path to credit `recharge_balance` only
- [x] 2.10 Update wallet serializers/API to expose bucket + `withdrawable_balance`
- [x] 2.11 Tests: migration invariant, verify command, meal debit order, withdraw blocked when only commission remains, after-balance snapshots

## 3. Referral domain models & indexes (HIGH)

- [x] 3.1 Implement `ReferralProfile` (1:1 customer, unique `BEF`+8 `code`, optional `share_count`/`last_shared_at`, `public_id`)
- [x] 3.2 Implement `ReferralRelationship` with required indexes (`referrer_id`, unique `referred_id`, attributed/created timestamp)
- [x] 3.3 Implement `ReferralCommission` with statuses `pending|success|failed|skipped|reversed`, reason fields, reversal linkage, manual flag, and indexes `(referrer_id, created_at)`, `(referred_id)`, `(order_delivery_id)`, `(status)`
- [x] 3.4 Implement lightweight `ReferralValidationEvent` (or equivalent) for conversion analytics
- [x] 3.5 Create migrations + Django admin registrations
- [x] 3.6 Implement `BEF`+8 code generator with collision retry + backfill command for existing customers

## 4. Eligibility & attribution services

- [x] 4.1 Implement eligibility helpers using `get_active_subscription` and inactive-referrer error message
- [x] 4.2 Implement `attribute_on_signup` (mobile-only, self-referral block, immutable unique referred, IntegrityError-safe)
- [x] 4.3 Extend `PendingCustomerRegistration` with `referral_code`, `referrer_snapshot_id`, and intent timing; store on mobile email register
- [x] 4.4 Wire attribution into `finalize_pending_registration` with mandatory eligibility re-check at finalize (snapshot audit-only)
- [x] 4.5 Wire attribution into phone OTP new-customer path
- [x] 4.6 Wire attribution into social `created_user=True` path only
- [x] 4.7 Reject web registration requests that include `referral_code` with `422`
- [x] 4.8 Ensure new customer factory paths always create `ReferralProfile`

## 5. Commission accrual, reversal, manual adjust (HIGH)

- [x] 5.1 Implement `credit_referral_commission_for_delivery` with status machine, dual subscription checks, percent calc, rounding, skip &lt; 0.01 as `skipped`
- [x] 5.2 Atomically debit Admin Wallet + credit referrer `commission_balance` + write `success` audit row; idempotency key `referral-commission:{delivery.public_id}`
- [x] 5.3 On Admin float shortfall: persist `failed` attempt; no user credit; do not block delivery
- [x] 5.4 Implement `reverse_referral_commission` (success → reversed, linked wallet + admin reversal txns, reason/actor, idempotent)
- [x] 5.5 Implement admin `manual_adjust_referral_commission` (+/−, required reason, audit)
- [x] 5.6 Hook accrual into `mark_delivery` after successful `charge_delivered_meal` (Onahar-style try/except)
- [x] 5.7 Add `reconcile_referral_commissions` for `failed`/missing accruals
- [x] 5.8 Tests: 5% success, skipped inactive, failed float, idempotent delivery, reverse once, manual adjust, meal-off no success

## 6. Customer referral APIs

- [x] 6.1 Implement `GET /referrals/me/` (code, link, usability, summary stats)
- [x] 6.2 Implement paginated `GET /referrals/me/referred-users/`
- [x] 6.3 Implement paginated `GET /referrals/me/commissions/` including status
- [x] 6.4 Implement `POST /referrals/validate/` with IP-based throttle + validation event recording
- [x] 6.5 Mount customer routes; OpenAPI schemas
- [x] 6.6 API tests for auth, ownership, validate success/failure/`429`

## 7. Admin referral APIs (finance + growth)

- [x] 7.1 Implement analytics including financial totals and conversion metrics (validations, registrations, paid-from-referral, conversion rate)
- [x] 7.2 Implement paginated filterable relationships and commissions lists (including status filter)
- [x] 7.3 Implement per-customer referral detail endpoint
- [x] 7.4 Implement CSV export for commission reports with finance columns
- [x] 7.5 Implement admin reverse + manual adjustment endpoints (required reason)
- [x] 7.6 Enforce `IsVerifiedAdmin`; OpenAPI; tests including non-admin denial and CSV content smoke checks

## 8. Medium enhancements & documentation

- [x] 8.1 Optional share tracking endpoint or field update path for `share_count` / `last_shared_at`
- [x] 8.2 Document future fraud metadata hooks (same phone / device id / email domain) without enforcing in v1
- [x] 8.3 Write `referrals/docs/backend/referral-affiliate-commission.md` (statuses, reversal, pending snapshot, indexes, verify command)
- [x] 8.4 Write frontend mobile integration guide (registration + validate throttle + wallet buckets)
- [x] 8.5 Update wallet docs for dual balances, after snapshots, and `verify_wallet_balance_consistency`
- [x] 8.6 Rollout checklist: migrate → verify wallets → backfill codes → enable attribution → enable accrual → monitor reconcile/reverse
