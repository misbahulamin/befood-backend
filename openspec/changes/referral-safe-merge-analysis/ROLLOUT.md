# Referral Integration — Staging / Production Rollout

Branch: `referral-integration` (based on `origin/main` + dual-bucket wallet + `referrals` app).

## Pre-deploy

1. Confirm EC2 / staging already has `wallet.0004_live_status_provider_recharge_ref_unique` applied.
2. Set `REFERRAL_ENABLED=False` in the environment before first deploy of this branch.
3. Take a DB backup before migrate.

## Deploy steps

1. Deploy application code with `REFERRAL_ENABLED=False`.
2. Run migrations (`admin_wallet.0005`, `wallet.0005_dual_bucket_balances`, `user_management.0021`, `referrals.0001`).
3. Run:

```bash
python manage.py verify_wallet_balance_consistency
python manage.py audit_wallet_accounting
```

Both must exit 0.

4. Backfill codes (attribution still off until you enable the flag):

```bash
python manage.py backfill_referral_profiles
```

5. Enable attribution only: set `REFERRAL_ENABLED=True` after smoke-testing registration paths. Commission accrual uses the same flag.
6. Monitor `reconcile_referral_commissions` / failed commission rows and Admin Wallet float.

## Rollback

1. **First:** set `REFERRAL_ENABLED=False` (stops new attribution and accrual; delivery still succeeds).
2. Do **not** reverse dual-bucket columns (`recharge_balance` / `commission_balance`) without a dedicated reverse migration and finance sign-off.
3. Code rollback to pre-dual-bucket is unsafe once `wallet.0005` is applied; keep dual-bucket-aware wallet code deployed even if referral is disabled.

## Safe defaults

| Setting | Staging first value | Notes |
|---------|---------------------|-------|
| `REFERRAL_ENABLED` | `False` then `True` | Kill switch |
| `REFERRAL_COMMISSION_PERCENT` | `5` | String decimal |
| `REFERRAL_LINK_BASE_URL` | product invite URL | Mobile share links |
