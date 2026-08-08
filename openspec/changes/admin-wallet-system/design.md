## Context

BeFood already has a customer `wallet/` ledger (1:1 with `CustomerProfile`) used for manual recharge/withdraw and meal-delivery debits via `orders.services.meal_payment.charge_delivered_meal`. Onahar tracks **meal units**, not BDT. Operational costs allocate BDT into meal pricing but are not a platform cash wallet. The `payments` app exists as stubs and is not mounted.

There is **no central platform cash wallet** today. Product needs a BeFood Admin Wallet as the platform’s financial control plane: automatic credits from successful customer payments, manual deposit/withdraw, expense posting, dashboard aggregates, filterable history, verified-admin auth, and auditability.

Stakeholders: verified admins (finance/ops), customer payment flows (indirect), future settlement/refund products, Admin Panel frontend.

Constraints:
- Ledger-first: append-only transactions; denormalized balance updated only in the same atomic ledger path.
- Decimal money (BDT), no floats; `PublicIdMixin` for API identities.
- Admin APIs under `/api/v1/web/...` with `IsVerifiedAdmin` (same pattern as onahar/admin customer).
- Business logic in `services/`; thin DRF views; OpenAPI + tests + docs in the same change.
- Avoid double-counting: customer wallet recharge is customer liability; meal charge that already entered via prior custody models must be defined carefully (see Decisions).

## Goals / Non-Goals

**Goals:**
- One singleton (or singleton-scoped) BeFood Admin Wallet with ledger-verified balance.
- Idempotent automatic credit when a meal-delivery customer payment succeeds.
- Manual deposit, withdrawal, and typed expense/adjustment operations with balance guards.
- Rich transaction metadata for source tracking and admin filters/search.
- Dashboard summary aggregates (current balance, today/month income & expense, totals).
- Audit log for sensitive mutations.
- Backend + frontend docs for Admin Panel Wallet UI.

**Non-Goals:**
- Full restaurant/rider settlement product workflows (provide typed expense postings + service hooks only).
- Payment gateway integration / mounting the `payments` app.
- Treating customer wallet **recharge** as Admin Wallet income in v1 (prevents double-count when later charging meals).
- Editing or deleting completed ledger rows.
- Mobile-only Admin Wallet routes.
- Multi-currency or multi-entity wallets (single BDT platform wallet).
- Automatic Onahar meal-unit → BDT conversion (Onahar remains meal ledger; cash Onahar expense is a manual/typed debit when ops pays cash).

## Decisions

### 1. New app: `admin_wallet/`
- **Choice:** Create `admin_wallet/` as a bounded context (models, services, web API, admin, tests, docs). Mount under `/api/v1/web/admin-wallet/`.
- **Rationale:** Platform cash must not share tables with customer liability wallets; clearer permissions and future settlement growth.
- **Alternatives considered:**
  - Extend `wallet/` with a “system wallet” row — risk of permission leaks and mixed semantics.
  - Put under `payments/` — that app is gateway-oriented and currently unmounted.

### 2. Singleton platform wallet
- **Choice:** One `AdminWallet` row (enforced via singleton pattern / unique constraint on a fixed `code=platform`). Authorized verified admins **manage** it; they do not each own a separate cash balance in v1.
- **Rationale:** Product describes “BeFood’s main financial wallet,” not per-admin petty cash.
- **Alternatives considered:** Per-admin wallets — deferred; can add later as sub-accounts without changing the central ledger pattern.

### 3. Append-only ledger + denormalized balance
- **Choice:** `AdminWalletTransaction` is append-only. Services `credit_admin_wallet` / `debit_admin_wallet` use `select_for_update` on the wallet row, write the ledger entry with `balance_after`, update `AdminWallet.balance` in the same `atomic()` block. Completed monetary fields are immutable via API.
- **Rationale:** Matches customer wallet and Onahar fund patterns; enables reconciliation (`sum(credits) - sum(debits) == balance`).
- **Alternatives considered:** Balance-only updates — fails audit/transparency requirements.

### 4. Transaction taxonomy
- **Choice:** Explicit `type` enum plus `direction` (`credit`|`debit`):
  - **Credit:** `customer_payment`, `manual_deposit`, `adjustment`, `refund_reversal`, `other_income`
  - **Debit:** `withdrawal`, `customer_refund`, `restaurant_settlement`, `rider_payment`, `operational_expense`, `onahar_expense`, `promotional_cost`, `platform_expense`, `manual_adjustment`
  - `status`: `pending` | `completed` | `failed` | `cancelled` (v1 mutations complete synchronously as `completed` unless a future async path needs pending)
  - `method`: `manual` | `wallet` | `bkash` | `nagad` | `other` (allowlist; extendable)
- **Rationale:** Matches product categories while keeping filterable machine enums.
- **Alternatives considered:** Free-text only types — weak filtering; over-normalized type tables — unnecessary for v1.

### 5. Source tracking fields
- **Choice:** Structured columns + JSON metadata:
  - `source` (short label/category), `reference` (human/machine ref string)
  - Optional FKs / public ids: `order`, `order_delivery`, `customer_profile`, `actor_admin` (AdminProfile), `customer_wallet_transaction`
  - `note`, `reason`, `idempotency_key` (unique on wallet), `external_ref`
- **Rationale:** Admin history can show “+৳1,200 | Customer Order Payment | Order #… / Delivery …” without parsing opaque notes.
- **Alternatives considered:** Metadata-only — harder to filter/index.

### 6. What auto-credits Admin Wallet in v1
- **Choice:** On successful `charge_delivered_meal` (customer wallet debit completed), call `admin_wallet.services.ingestion.credit_from_meal_payment(delivery, customer_txn)` with idempotency key `meal-payment:{delivery.public_id}` (or customer txn public_id). Type=`customer_payment`, method=`wallet`, link order/delivery/customer/customer txn.
- **Failure policy:** Prefer **same atomic block** as customer charge when practical so platform ledger stays consistent; if import-cycle forces a post-commit hook, failures MUST be logged and a reconcile command MUST be able to backfill missing credits without double-posting. Design preference: **same atomic transaction** as mark-delivered charge (like wallet debit), with try/except only if a hard cycle appears—then document + reconcile.
- **Not auto-credited in v1:** customer wallet `recharge` (liability/custody; would double-count when meal is later charged).
- **Future:** gateway order payments credit with type `customer_payment` and method=`bkash`/`nagad`, idempotency on payment intent id.
- **Rationale:** Product example “Customer Order/Wallet Payment” maps to meal charges paid from customer wallet; recharge-as-income is an accounting trap.
- **Alternatives considered:** Credit on recharge instead of meal charge — wrong for revenue timing and double-count risk.

### 7. Manual deposit / withdrawal / expenses
- **Choice:** Service APIs:
  - `manual_deposit(amount, reason, note, admin)` → credit `manual_deposit`
  - `withdraw(amount, reason, note, admin)` → debit `withdrawal` if `amount <= balance`
  - `post_expense(type, amount, reason, note, admin, refs…)` → debit typed expense
  - `adjust(...)` → credit `adjustment` or debit `manual_adjustment` (restricted)
- All create audit log rows with previous/new balance.
- **Rationale:** Clear admin operations matching product §§4–6.
- **Alternatives considered:** Generic “create transaction” endpoint — too easy to misuse; prefer purpose-built actions.

### 8. Aggregates for dashboard
- **Choice:** Compute summaries in a query service from completed ledger rows (with date bounds in project timezone), optionally cache denormalized lifetime counters on `AdminWallet` updated in the ledger path (`total_received`, `total_manual_added`, `total_withdrawn`, `total_expenses`, `total_customer_payments`) for fast cards. Lifetime counters MUST stay in sync inside the same transaction as ledger writes; dashboard “today/month” always from ledger queries.
- **Rationale:** Fast cards without sacrificing correctness for period filters.
- **Alternatives considered:** Pure live SUM only — fine at small scale; counters help as volume grows.

### 9. Authorization
- **Choice:** All Admin Wallet endpoints require `IsVerifiedAdmin`. Optionally introduce permission codenames (e.g. `admin_wallet.deposit`, `admin_wallet.withdraw`, `admin_wallet.expense`, `admin_wallet.view`) via existing group permission helpers when the project already uses them; otherwise v1 may allow any verified admin to view and mutate, with audit as the control—**prefer role split if `HasGroupPermission` wiring is low-cost**.
- **Rationale:** Product requires verified-admin-only + possible deposit/withdraw role split.
- **Alternatives considered:** Superuser-only mutations — too narrow for ops.

### 10. Audit log
- **Choice:** `AdminWalletAuditLog` append-only: actor, action, amount, previous_balance, new_balance, reason, transaction FK, timestamps. Written for deposit, withdraw, expense, adjustment (and any future edit attempts—which v1 rejects).
- **Rationale:** Explicit audit trail beyond the money ledger.
- **Alternatives considered:** Reuse generic admin audit if one exists—prefer dedicated table for financial fields.

### 11. Idempotency
- **Choice:** Unique `(wallet, idempotency_key)` where key is required for automated ingestion and optional for manual ops (manual can pass `Idempotency-Key` header). Replay returns the original completed transaction.
- **Rationale:** Prevents duplicate credits from delivery retries (same class of bug customer wallet already solved).

### 12. API surface (v1)
- **Web (IsVerifiedAdmin):**
  - `GET /api/v1/web/admin-wallet/` — wallet summary + lifetime totals
  - `GET /api/v1/web/admin-wallet/dashboard/` — period cards (today/month) + recent transactions
  - `GET /api/v1/web/admin-wallet/transactions/` — paginated, filterable, searchable
  - `GET /api/v1/web/admin-wallet/transactions/{public_id}/`
  - `POST /api/v1/web/admin-wallet/deposits/`
  - `POST /api/v1/web/admin-wallet/withdrawals/`
  - `POST /api/v1/web/admin-wallet/expenses/`
  - `GET /api/v1/web/admin-wallet/audit-logs/`
- Filters: date range, direction, type (or type group), method, status, `q` (transaction public_id, order public_id, customer identifiers as allowlisted).
- **Rationale:** Resource-oriented actions under web admin prefix.

### 13. Docs
- **Choice:** `admin_wallet/docs/backend/admin-wallet.md` + `admin_wallet/docs/frontend/admin-wallet.md` following project doc rules.
- **Rationale:** Admin Panel can integrate without reading OpenSpec alone.

## Risks / Trade-offs

- **[Risk] Double-counting if recharge and meal charge both credit Admin Wallet** → Mitigation: v1 credits only meal-payment ingestion; document recharge as out of scope.
- **[Risk] Admin Wallet credit failure after customer debit** → Mitigation: prefer same atomic block; provide `reconcile_admin_wallet_meal_payments` management command.
- **[Risk] Expense types used as ad-hoc settlement without real settlement entities** → Mitigation: accept typed expenses as v1; link optional order/customer refs; full settlement apps later.
- **[Risk] Broad verified-admin write access** → Mitigation: audit logs + optional permission codenames; never expose to customers.
- **[Risk] Large history list performance** → Mitigation: indexes on `(wallet, -created_at)`, type, status, created_at; pagination required.

## Migration Plan

1. Add `admin_wallet` app + migrations (wallet singleton seed, ledger, audit).
2. Wire URLs and permissions; ship read APIs first if needed, then mutations.
3. Hook meal-payment ingestion; backfill optional via reconcile for historical delivered charges (product decision: backfill vs start-from-deploy; default **start-from-deploy**, reconcile available).
4. Deploy; verify with tests + admin smoke on dashboard/deposit/withdraw.
5. Rollback: disable hook flag `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` without dropping ledger tables.

## Open Questions

- Should historical meal payments before deploy be backfilled into Admin Wallet, or start at zero at cutover? (Default: start at cutover.)
- Exact permission codenames / which admin groups may withdraw vs only view?
- Should cash Onahar distributions auto-post `onahar_expense`, or remain manual until a cash payout workflow exists? (Default: manual typed expense.)
