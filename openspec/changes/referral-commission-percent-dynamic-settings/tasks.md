## 1. Backend model and migration

- [x] 1.1 Add singleton `ReferralProgramSettings` (`pk=1`, `commission_percent` 0–100 Decimal, `updated_at`, `.load()` / save guard) in `referrals/models.py`
- [x] 1.2 Create migration seeding `commission_percent` from `REFERRAL_COMMISSION_PERCENT` (default `5.00`); do not alter existing `ReferralCommission` rows
- [x] 1.3 Register model in `referrals/admin.py` (read/update for ops parity with other settings)

## 2. Backend services

- [x] 2.1 Add `referrals/services/settings.py` with `get_referral_program_settings()` and `update_referral_commission_percent(...)` including 0–100 / 2-dp validation
- [x] 2.2 Change `commission_percent()` in `referrals/services/commission.py` to read the singleton (env only as seed/fallback on first create)
- [x] 2.3 Confirm accrual / in-place skip-upgrade paths keep using `commission_percent()` inside the existing atomic transaction (no historical rewrite)

## 3. Backend admin API

- [x] 3.1 Add serializer for `referral_commission_percent` + `updated_at`
- [x] 3.2 Add `IsVerifiedAdmin` `GET|PATCH` view for referral settings
- [x] 3.3 Mount at `GET|PATCH /api/v1/web/referrals/settings/` in `referrals/api/web_urls.py`
- [x] 3.4 Add OpenAPI helpers / examples for the new endpoints

## 4. Backend tests and docs

- [x] 4.1 Tests: singleton seed, GET/PATCH success, invalid percent rejected, non-admin denied
- [x] 4.2 Tests: after PATCH to new percent, new accrual uses new rate; prior SUCCESS row unchanged
- [x] 4.3 Update `referrals/docs/backend/referral-affiliate-commission.md` (percent source = DB settings)
- [x] 4.4 Add/update frontend contract doc for Admin Settings (`referrals/docs/frontend/`) with request/response examples
- [x] 4.5 Comment `REFERRAL_COMMISSION_PERCENT` in `core/settings/base.py` as seed/fallback only

## 5. Admin Frontend (settings page)

- [x] 5.1 Locate `/admin/settings` structure and existing settings API patterns (e.g. order-wallet-settings)
- [x] 5.2 Add Referral Settings section / `ReferralCommissionSetting` component (load, edit, save, toasts)
- [x] 5.3 Wire `GET|PATCH /api/v1/web/referrals/settings/` with admin auth + `X-Client-Type: web`
- [x] 5.4 Client validation 0–100; surface backend errors; verified-admin-only route gating

## 6. Verification and rollout

- [x] 6.1 Run referral unit/API tests related to commission percent and settings
- [x] 6.2 Staging checklist: GET shows value; PATCH updates; one new delivery commission uses new %; historical SUCCESS unchanged; wallets untouched
- [x] 6.3 Confirm no reconcile/backfill job recalculates old commissions after percent change
