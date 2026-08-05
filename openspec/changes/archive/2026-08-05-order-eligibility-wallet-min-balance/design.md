## Context

BeFood already creates meal package orders through `create_meal_order` in `orders/services/order_service.py`. That path already calls `check_existing_monthly_lock(customer, order_month)`, which rejects a second non-cancelled order (`pending` / `confirmed` / `active` / `completed`) for the same `YYYY-MM` `order_month`. Customer API tests already cover the happy path for that lock.

Customers also have wallets (`wallet.Wallet`: balance, status `active`/`frozen`). Wallet funding exists, but order creation does **not** yet require a minimum balance. Ops want a prepaid floor (default 500 BDT) that admins can change without redeploying, using the same singleton settings pattern as `MealOffSettings` and `MenuRevealSettings`.

Stakeholders: verified customers (mobile/web order flow), verified admins (settings + ops), kitchen/ops (one package per customer per month).

## Goals / Non-Goals

**Goals:**

- Confirm and document same-month package exclusivity as a stable contract; close any gaps found during audit.
- Enforce wallet minimum balance before order creation succeeds.
- Let verified admins configure that minimum via API (+ Django admin).
- Clear customer-facing validation errors for month-lock and insufficient/frozen wallet.
- Keep services thin-view / service-layer-first, consistent with existing order and meal-off settings.

**Non-Goals:**

- Debiting wallet / charging order total from wallet (checkout payment remains deferred).
- Changing recharge/withdraw APIs or ledger schema.
- Multi-currency thresholds (BDT only, matching wallet).
- Changing how `order_month` is computed or delivery generation.
- Soft “warning only” UX without server enforcement.

## Decisions

### 1. Keep month-lock in `create_meal_order`; audit first, change only if broken

**Choice:** Treat existing `check_existing_monthly_lock` as the source of truth. Audit statuses, cancelled re-order, and API mapping; add missing unit/API coverage if gaps appear. Do not invent a parallel lock in the serializer.

**Alternatives considered:**
- DB unique constraint on `(customer, order_month)` — too strict because cancelled orders must allow a replacement.
- Lock only `monthly` meal types — product already locks **any** package for that calendar month (daily/weekly/monthly share `order_month`); user request matches “one package this month,” so keep current semantics.

### 2. Wallet minimum check runs after month-lock, inside the same service transaction path

**Choice:** In `create_meal_order`, order of gates:

1. Meal active + priced  
2. Month lock  
3. Wallet minimum eligibility  
4. Create order + deliveries  

Raise a dedicated `InsufficientWalletBalanceError` (and treat frozen wallet as ineligible). Map to serializer validation errors like `MonthLockError`.

**Alternatives considered:**
- Check only in the serializer — weaker; bypassable if service is called elsewhere (tests already call the service).
- Debit package price at create time — out of scope; user asked for a **minimum presence** gate, not payment.

### 3. New `OrderWalletSettings` singleton on `orders` (not wallet app)

**Choice:** Add `OrderWalletSettings` with `pk=1` load/get_or_create pattern and field `min_wallet_balance_to_order` (`Decimal`, default `500.00`, `MinValueValidator(0)`). Mount admin API next to meal-off settings, e.g. `GET|PATCH /orders/order-wallet-settings/` with `IsVerifiedAdmin`.

**Rationale:** The rule is an **order eligibility** policy; wallet remains the balance source of truth. Mirrors `MealOffSettings` ownership in `orders/`.

**Alternatives considered:**
- Put setting on `wallet` — couples funding domain to order policy.
- Env/settings.py constant — not admin-editable.
- Extend `BusinessSettings` — different domain and less consistent with meal-off/menu-reveal singletons.

### 4. Missing wallet = balance 0; frozen = reject

**Choice:** If no `Wallet` row exists, treat balance as `0.00` (or get-or-create inactive zero wallet consistently with wallet GET behavior — prefer **read without side-effect create** during order gate to avoid surprising wallet creation on failed orders; use `getattr(customer, 'wallet', None)` / `Wallet.objects.filter(...).first()`). Frozen wallets MUST fail the gate even if balance ≥ minimum.

**Alternatives considered:**
- Auto-create wallet on order attempt — side effect on a failing path; prefer wallet GET/recharge flows for creation.
- Allow frozen with balance — unsafe for ops intent.

### 5. Comparison is balance ≥ minimum (inclusive)

**Choice:** `balance >= min_wallet_balance_to_order`. Exact equality (e.g. 500.00 when min is 500.00) MUST pass.

### 6. Error messaging and HTTP status

**Choice:** Keep existing month-lock message. For wallet gate, return `400` with a stable, operator-safe message including the required minimum (and optionally current balance) in the detail string or structured `errors` field — match project serializer validation shape used by month-lock (`non_field_errors`). Do not invent a new problem+json format in this change unless the project already uses it on order create.

### 7. Optional customer read of the minimum (recommended)

**Choice:** Expose the configured minimum on a lightweight customer-readable surface so the app can show “need at least X before order” — either:
- include `min_wallet_balance_to_order` on `GET /wallet/`, or  
- a small public-to-customer settings read on orders.

Prefer **adding a read-only field on wallet GET** (or a dedicated customer-safe endpoint) so the order create response is not the only place customers learn the rule. Admin PATCH remains admin-only.

If wallet GET enrichment is undesirable, document that clients learn the amount from the 400 error until a follow-up. Prefer wallet GET enrichment for better UX.

## Risks / Trade-offs

- **[Risk] Existing tests that create orders without funding a wallet will start failing** → Mitigation: update fixtures/helpers to credit wallets (or set min to 0 in those tests); seed default 500 only in production-like settings load.
- **[Risk] Admins set minimum extremely high and block all orders** → Mitigation: validate `>= 0`; document ops guidance; no hard upper cap unless product asks (optional soft max e.g. 100000).
- **[Risk] Race: two concurrent order creates bypass month-lock** → Mitigation: existing gap; optional `select_for_update` on customer orders in a follow-up; for this change, keep current filter `.exists()` unless audit finds easy fix with low risk.
- **[Risk] Confusion that wallet gate means payment** → Mitigation: docs and OpenAPI state eligibility-only; no ledger `payment` row on order create.
- **[Trade-off] Inclusive ≥ vs exclusive >** → Inclusive matches “at least 500” language.

## Migration Plan

1. Add `OrderWalletSettings` migration with default `500.00`.
2. Deploy code that reads settings with `load()` (get_or_create).
3. Wire wallet check into `create_meal_order`.
4. Mount admin settings endpoint; register Django admin.
5. Update order/wallet tests and docs.
6. Rollback: revert deploy; settings row is harmless if unused. Feature flag not required.

## Open Questions

- None blocking — assume BDT decimal strings, default 500.00, eligibility-only (no debit), and month-lock applies to any package type for that `order_month` (current behavior).
- Nice-to-have during apply: whether to surface min on `GET /wallet/` vs only admin settings + error message (design prefers wallet GET enrichment).
