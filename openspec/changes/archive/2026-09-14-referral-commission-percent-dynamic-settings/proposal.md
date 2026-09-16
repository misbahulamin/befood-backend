## Why

Referral commission percentage is currently read from Django settings / env (`REFERRAL_COMMISSION_PERCENT`, default `5`) inside `referrals/services/commission.py`. Business cannot change the rate from the admin panel without a deploy. Now that referral accrual is live, ops need a verified-admin–editable rate that applies only to **future** commissions, without rewriting historical commission rows or wallet balances.

## What Changes

- Persist the active referral commission percentage in a **database-backed singleton settings** model (same pattern as `OrderWalletSettings` / `MealOffSettings`), seeded from the current env default (`5`).
- Change `commission_percent()` to read the live DB value (with env as bootstrap / fallback for first load), not a process-static env constant alone.
- Add verified-admin **GET/PATCH** web API for referral settings so Admin Frontend `/admin/settings` can view and update the percentage.
- Validate percentage **0–100** (inclusive) with at most 2 decimal places; reject invalid updates with 400/422.
- Snapshot the rate used onto each new `ReferralCommission.commission_percent` at accrual time (already stored); **never** recalculate or mutate existing successful/failed/skipped/reversed rows when the setting changes.
- Document backend + Admin Frontend integration for the settings page section “Referral Settings”.
- Keep env `REFERRAL_COMMISSION_PERCENT` as **initial seed / emergency fallback only** after DB row exists (not the primary runtime source once seeded).

## Capabilities

### New Capabilities

- `referral-commission-settings`: Database-backed referral commission percentage, verified-admin GET/PATCH API, validation, and future-only application to accrual calculation.
- `referral-settings-admin-ui`: Admin Frontend `/admin/settings` Referral Settings section that loads, edits, and saves the commission percentage via the new API.

### Modified Capabilities

- (none in `openspec/specs/` — referral commission rate was previously env-only under the affiliate change; this introduces new capability specs rather than delta-editing archived main specs)

## Impact

- **Backend:** `referrals/models.py` (new singleton settings), migration, `referrals/services/commission.py` (`commission_percent()`), new settings service + admin API views/serializers/urls/openapi, tests, docs under `referrals/docs/`.
- **Config:** `core/settings/base.py` — keep `REFERRAL_COMMISSION_PERCENT` for seed/fallback; document that runtime rate is DB-driven.
- **Admin Frontend (separate repo, `localhost:5173`):** `/admin/settings` — new Referral Settings UI component calling web API (mirror `order-wallet-settings` pattern).
- **Production safety:** no wallet rewrite, no historical commission recalculation, backward-compatible migration with default `5.00`.
- **Permissions:** `IsVerifiedAdmin` only (same as other admin settings endpoints).
