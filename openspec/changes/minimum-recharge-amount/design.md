## Context

Recharge today: `WalletRechargeView.post` → `RechargeRequestSerializer` (`_validate_funding_amount`, min 0.01) → `funding.request_recharge` (no minimum) → PENDING `WalletTransaction` (no balance change) → admin approve credits. Settings: `OrderWalletSettings` singleton (pk=1, `load()`), 3 thresholds with strict ordering `subscribe > reminder > stop >= 0`, admin `OrderWalletSettingsView` GET/PATCH + `update_order_wallet_settings`. `WalletSerializer` already exposes 3 thresholds in wallet summary — natural 4th field. Frontend `AdminSettingsPage.tsx` has established Card/Input/normalize/PATCH/toast/refetch pattern. Mobile wallet uses cubit+service+DTO with `recharge_amount_step` widget.

## Goals / Non-Goals

Goals: one canonical Decimal field default 500.00; backend enforcement at request time; admin-editable; clients read from backend, never hardcode; pending/historical rows untouched.
Non-goals: approval/credit/withdraw/meal-stop/delivery-fee changes; new settings table; retroactive invalidation.

## Decisions

1. **Reuse `OrderWalletSettings`, new field `minimum_recharge_amount`** — Decimal(12,2), default 500.00, `MinValueValidator(0.00)`. Alternative (new table / `AppVersionSettings`) rejected: unnecessary table, wrong domain.
2. **Enforce in `funding.request_recharge` after `validate_amount`, before wallet lock** — covers all callers; Decimal `<` comparison; new `RechargeBelowMinimumError(WalletError, code=RECHARGE_BELOW_MINIMUM)` carrying `minimum`; view maps to 400 `{detail, code, minimum_recharge_amount}`.
3. **Independent of threshold ordering** — minimum recharge is a request floor, not part of `subscribe > reminder > stop` chain; separate `>= 0` + 2dp validation so admin can set 700/300/100 freely.
4. **Expose via wallet summary** — add `minimum_recharge_amount` to `WalletSerializer` (same `_threshold_str` helper); admin serializer/view already generic. No new endpoint.
5. **Concurrency** — read current setting inside `request_recharge` transaction each call; stale clients still rejected authoritatively; error returns fresh minimum so clients can refresh.

## Risks / Trade-offs

- Existing `OrderWalletSettingsSerializer` must accept/render new field; PATCH stays partial.
- Admin lowering minimum never invalidates old pendings (by design — only `request_recharge` checks).
- Mobile offline cached value may be stale → backend error fallback with Bangla copy required.

## Migration

Additive `AlterModel`/`AddField` on `OrderWalletSettings` with `default=500.00`; existing singleton row backfilled 500.00. Rollback = reverse migration (drop column); code tolerates missing attr via `getattr` fallback only during deploy window.

## Open Questions

- Exact Bangla UX copy (propose `সর্বনিম্ন রিচার্জ ৳{min}।` + `৳{min}-এর কম রিচার্জ করা যাবে না।`).
- Whether admin wants an upper sanity cap (e.g. ≤ MAX_FUNDING_AMOUNT) — recommend yes, reuse 100000 cap.
