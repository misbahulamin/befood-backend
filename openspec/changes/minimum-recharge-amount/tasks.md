## 1. Backend (source of truth)
- [x] Migration `0020_orderwalletsettings_minimum_recharge` — add `minimum_recharge_amount` Decimal(12,2) default 500.00 (+ admin/docs note).
- [x] `orders/models.py` — field + help_text; keep `load()` singleton.
- [x] `orders/services/order_wallet_settings.py` — accept/validate `minimum_recharge_amount` in `update_order_wallet_settings` (≥0, 2dp, ≤ MAX_FUNDING); NOT in ordering chain.
- [x] `orders/api/serializers.py` — expose field in `OrderWalletSettingsSerializer`.
- [x] `wallet/services/funding.py` — `RechargeBelowMinimumError` + check in `request_recharge` after `validate_amount` (Decimal `<`).
- [x] `wallet/services/ledger.py` — export error mapping if needed (no change to `validate_amount` caps).
- [x] `wallet/api/views.py` — map new error → 400 `{detail, code, minimum_recharge_amount}`; extend schema docs.
- [x] `wallet/api/serializers.py` — add `minimum_recharge_amount` to `WalletSerializer` via `get_order_wallet_settings`.
- [x] Backend tests: default 500; 499.99 reject / 500.00 accept / 500.01 accept; admin update immediate effect; invalid admin values; unauthorized denied; old pending untouched; Decimal boundary.

## 2. Admin web (`F:\befood\befood-frontend`)
- [x] `types/orderWalletSettingsTypes.ts` + `adminOrderWalletSettingsApi.ts` — add field.
- [x] `useAdminOrderWalletSettings.ts` — include field in cache/mutation.
- [x] `AdminSettingsPage.tsx` — 4th input "Minimum Recharge Amount (BDT)", reuse `normalizeAmount`, independent validation, save/field-error/toast/refetch.
- [ ] Admin tests: load current, save valid, reject negative/non-numeric, error mapping.

## 3. Customer web
- [x] Wallet hook/query surfaces `minimum_recharge_amount` from wallet summary.
- [x] Recharge form: show `সর্বনিম্ন রিচার্জ ৳{min}`, live validation below-min, disable submit, exact-min valid, backend `RECHARGE_BELOW_MINIMUM` mapped + refresh cached min.
- [ ] Tests for above.

## 4. Mobile (`F:\befood\befood_mobile`)
- [x] `wallet_dto.dart`/`wallet_models.dart` — parse `minimum_recharge_amount`.
- [x] `wallet_service.dart` + `wallet_cubit.dart` — expose + refresh.
- [x] `recharge_amount_step` widget — live Bangla validation, block submit below min, exact-min allowed, backend error fallback.
- [ ] Tests for above.

## 5. Docs + rollout
- [x] Update wallet/settings docs (backend + frontend).
- [ ] Deploy order: backend migration+validation → admin UI → customer web → mobile. Rollback: reverse migration; clients fall back to 500.00 display if field absent.
