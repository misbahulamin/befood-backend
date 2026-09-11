## 1. Branch hygiene (before any port)

- [x] 1.1 Fetch remotes and fast-forward local `main` to `origin/main`
- [x] 1.2 Create backup branch `backup/unfinished-features-135e5e7` from `unfinished-features`
- [x] 1.3 Create integration branch `referral-integration` from `origin/main`
- [x] 1.4 Confirm production tip includes `wallet/migrations/0004_live_status_provider_recharge_ref_unique.py`

## 2. Wallet migration rewrite (do first)

- [x] 2.1 Port dual-bucket schema as new `wallet/migrations/0005_dual_bucket_balances.py` depending on `0004_live_status_provider_recharge_ref_unique`
- [x] 2.2 Remove or never add UF's colliding `0004_dual_bucket_balances.py` filename
- [x] 2.3 Renumber/fold UF `0005_referral_affiliate_system` helptext alters into `0005` or `0006` after live-status `0004`
- [x] 2.4 Port `admin_wallet/migrations/0005_referral_commission_types.py` unchanged in number (depends on admin_wallet `0004`)
- [x] 2.5 Port `user_management/migrations/0021_referral_affiliate_system.py` and `referrals/migrations/0001_referral_affiliate_system.py`
- [x] 2.6 Run `makemigrations --check` / migrate on a disposable DB clone and verify graph has no duplicate leaves

## 3. Compose wallet code (keep both sides)

- [x] 3.1 Integrate `wallet/models.py`: dual buckets + commission txn types + production live-status UniqueConstraint
- [x] 3.2 Port `wallet/services/ledger.py` bucket strategies from UF
- [x] 3.3 Integrate `wallet/services/funding.py`: bucket withdraw/approve/reject **plus** live `_provider_ref_taken` **plus** `maybe_resume_after_wallet_credit`
- [x] 3.4 Integrate `wallet/api/serializers.py`: bucket fields + `withdrawable_balance` + `meal_service_restored`
- [x] 3.5 Keep both management commands: `audit_wallet_accounting` and `verify_wallet_balance_consistency`
- [x] 3.6 Update `wallet/docs/backend/customer-wallet.md` to describe dual buckets without dropping hotfix docs notes

## 4. Port referral domain and hooks

- [x] 4.1 Copy `referrals/` app (models, services, api, admin, tests, docs, management commands)
- [x] 4.2 Register `referrals` in `INSTALLED_APPS` and add `REFERRAL_*` settings
- [x] 4.3 Mount referral URLs in `core/urls.py` without dropping main's web dashboard mount
- [x] 4.4 Port `PendingCustomerRegistration` referral fields and keep main's city default in `user_management/models.py`
- [x] 4.5 Port attribution hooks in customer_factory / phone_otp / google_oauth / facebook_oauth / pending_registration + related serializers/views
- [x] 4.6 Port `mark_delivery` referral commission hook in `orders/services/order_delivery.py`
- [x] 4.7 Port Admin Wallet referral commission type enums in `admin_wallet/models.py`

## 5. Verification gates

- [x] 5.1 Run `verify_wallet_balance_consistency` on migrated clone (expect exit 0)
- [x] 5.2 Run `audit_wallet_accounting` smoke on clone
- [x] 5.3 Run wallet funding/manual funding tests including provider-ref reuse and meal-service resume approve cases
- [x] 5.4 Run referral unit/API tests from UF against integration branch
- [x] 5.5 Run delivery/subscription tests that touch wallet charge + mark_delivery
- [x] 5.6 Confirm `db.sqlite3` is not staged

## 6. Rollout checklist (staging → production)

- [ ] 6.1 Staging deploy with `REFERRAL_ENABLED=False` — **ops / human**
- [ ] 6.2 Apply migrations; run verify commands — **ops on staging/prod**
- [ ] 6.3 Backfill referral profiles; enable attribution only — **ops**
- [ ] 6.4 Enable commission accrual; monitor reconcile/failed commissions — **ops**
- [x] 6.5 Document rollback: disable flag first; do not reverse dual-bucket columns without dedicated plan (`openspec/changes/referral-safe-merge-analysis/ROLLOUT.md`)
