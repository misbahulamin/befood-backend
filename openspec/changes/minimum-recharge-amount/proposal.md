## Why

Customer recharge currently has no minimum limit (only generic 0.01–100000 validation). Business requires a default minimum recharge of 500 BDT, admin-configurable from `/admin/settings`, with backend as source of truth for web + mobile.

## What Changes

- Add `minimum_recharge_amount` (Decimal, default `500.00`) to the `OrderWalletSettings` singleton.
- Enforce `amount >= minimum_recharge_amount` in `request_recharge` (service layer, Decimal comparison); serializer keeps generic checks.
- Expose the value in `GET Wallet` summary + admin `OrderWalletSettings` GET/PATCH; error code `RECHARGE_BELOW_MINIMUM` with current minimum.
- Admin Settings page: new "Minimum Recharge Amount (BDT)" control following existing threshold pattern.
- Customer web + mobile: load minimum from backend (wallet summary), inline validation, disable submit below minimum, map backend error.

## Capabilities

### New Capabilities
- `minimum-recharge-amount`: canonical minimum recharge setting, backend enforcement, client presentation.

### Modified Capabilities
- None (additive only; existing thresholds, approval flow, ledger untouched).

## Impact

- Backend: `orders` (settings model/service/serializer/view/migration), `wallet` (funding service, serializers, views).
- Frontend `F:\befood\befood-frontend`: `AdminSettingsPage`, `adminOrderWalletSettingsApi`, wallet/recharge hooks + customer recharge form.
- Mobile `F:\befood\befood_mobile`: `lib/wallet/*` service/DTO/cubit + recharge amount step widget.
- No change to approval flow, credit logic, pending/historical rows, meal block logic.
