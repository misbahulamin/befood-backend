## Context

`admin_wallet` is live as a platform cash ledger. Investigation of the reported bug (“customer recharge does not add to Admin Wallet”) shows:

| Path | Current behavior | Evidence |
|------|------------------|----------|
| Customer `recharge_wallet` | Credits customer `wallet` only | No Admin Wallet call in `wallet/services/ledger.py` |
| Meal `charge_delivered_meal` | Debits customer wallet + credits Admin Wallet via `credit_from_meal_payment` | `orders/services/meal_payment.py` |
| Spec/test | Recharge MUST NOT credit Admin Wallet | `admin-wallet-payment-ingestion` + `test_customer_recharge_does_not_credit_admin_wallet` |

v1 chose meal-time cash recognition to avoid double-count if both recharge and meal credited. Ops expect cash-in at recharge time. This change flips timing to **custody accounting** without double-counting.

Stakeholders: verified admins (finance/ops), customer funding APIs, meal delivery charging, Admin Panel Wallet UI.

Constraints: Decimal BDT; append-only ledger; `select_for_update`; services layer; idempotency; no float money; keep customer recharge/withdraw API shapes stable.

## Goals / Non-Goals

**Goals:**
- Auto-credit Admin Wallet on successful customer recharge (same amount, same atomic block when practical).
- Auto-debit Admin Wallet on successful customer withdraw (custody out).
- Stop meal-delivery path from cash-crediting Admin Wallet (prevent double-count).
- Keep meal revenue visible for admin reporting without increasing cash balance again.
- Idempotent keys, reconcile/backfill, docs + tests updated.

**Non-Goals:**
- Live bKash/Nagad gateway mounting (still reserved methods).
- Full double-entry GL / separate liability sub-ledger product.
- Changing customer wallet public API request/response contracts.
- Multi-currency or per-admin wallets.
- Automatically reversing historical meal `customer_payment` cash credits (optional ops tool only).

## Decisions

### 1. Accounting model: cash at funding, revenue at meal without second cash credit
- **Choice:** Admin Wallet **balance** moves on customer funding in/out and on existing admin ops (deposit/withdraw/expense). Meal delivery charges **do not** call `credit_admin_wallet` for cash.
- **Rationale:** Matches ops expectation (“recharge → our wallet up”) and avoids recharge+meal double-count.
- **Alternatives considered:**
  - Keep meal-only credit — rejects the reported product need.
  - Credit both recharge and meal — double-counts.

### 2. New transaction types for funding custody
- **Choice:** Add credit type `customer_funding` and debit type `customer_withdraw` (names exact in implementation). Allowlist in `CREDIT_TYPES` / `DEBIT_TYPES`. Lifetime counters: add `total_customer_funding` (and optionally `total_customer_withdrawals`) on `AdminWallet`, or map funding into `total_received` with clear docs—**prefer dedicated counters** so manual deposits stay distinct.
- **Rationale:** Filterable history; does not overload `customer_payment` (meal revenue semantics).
- **Alternatives considered:** Reuse `customer_payment` for recharge — confuses meal vs funding.

### 3. Ingestion hooks from customer wallet services
- **Choice:** After successful completed recharge/withdraw in `wallet.services.ledger`, call `admin_wallet.services.ingestion.credit_from_customer_recharge` / `debit_from_customer_withdraw` inside the same `transaction.atomic` (lazy import to avoid cycles, same pattern as meal payment).
- **Idempotency:** `customer-recharge:{wallet_txn.public_id}` and `customer-withdraw:{wallet_txn.public_id}`.
- **Flags:** `ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED` (default `True`). Meal flag `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` becomes unused for cash credit (default `False` or remove call site).
- **Alternatives considered:** Django signals — harder to keep same atomic block; post-commit hooks — need heavier reconcile.

### 4. Meal path: revenue recognition without cash credit
- **Choice:** Remove/no-op `credit_from_meal_payment` cash credit. Record meal revenue for dashboards via either:
  - **Preferred:** aggregate from charged `OrderDelivery` / customer `WalletTransaction(type=payment)` for `total_customer_payments` / period meal-revenue cards, **or**
  - append-only recognition rows that **do not** change `AdminWallet.balance` (only if a dedicated model/field is justified).
- Prefer **query-based meal revenue** in v1 of this change to avoid fake ledger credits. Keep optional history note in docs that meal cash credits were the old model.
- **Rationale:** Balance stays custody-correct; meal revenue still reportable.
- **Alternatives considered:** Net-zero paired debit/credit ledger rows per meal — good audit, more complexity; defer unless UI requires meal rows inside Admin Wallet transaction list.

### 5. Customer withdraw vs Admin Wallet insufficient balance
- **Choice:** Attempt Admin Wallet debit in the same atomic block as customer withdraw. If Admin Wallet has insufficient balance, **fail the customer withdraw** with a clear domain error (mapped to `409`/`422`) so custody cannot go negative. Ops must `manual_deposit` (or reduce expenses) to restore float.
- **Rationale:** Keeps Admin Wallet non-negative invariant; surfaces real float problems early.
- **Alternatives considered:** Best-effort admin debit + alert — silent drift; allow negative admin balance — breaks ledger guards.

### 6. Dashboard semantics
- **Choice:**
  - `balance` / today-month **income** include `customer_funding` credits (and manual deposits, etc.).
  - `total_customer_payments` (or renamed display doc: “Meal revenue recognized”) reflects meal charges, **not** funding credits.
  - Document card mapping in frontend docs so UI does not label funding as “order payment.”
- **Rationale:** Separates cash-in from meal revenue.

### 7. Cutover / historical data
- **Choice:** Default **forward-only** for funding credits from deploy. Provide `reconcile_admin_wallet_customer_funding` management command (dry-run supported) to backfill missing funding credits/debits by scanning completed customer recharge/withdraw txns. Do **not** auto-delete prior meal `customer_payment` cash credits; document optional manual adjustment / ops review if balances look inflated after backfill.
- **Rationale:** Safe default; ops can choose backfill after reviewing double-count risk with old meal credits.

### 8. Tests & docs
- **Choice:** Replace `test_customer_recharge_does_not_credit_admin_wallet` with recharge/withdraw custody tests; update meal test to assert **no second cash credit** (balance unchanged by meal when funding already credited, or no new cash credit row). Update `admin_wallet/docs/{backend,frontend}/admin-wallet.md` and wallet backend docs cross-links.
- **Rationale:** Specs and tests currently encode the opposite product rule.

## Risks / Trade-offs

- **[Risk] Inflated Admin Wallet if old meal cash credits remain and funding is backfilled** → Mitigation: forward-only default; reconcile docs warn; optional adjustment playbook.
- **[Risk] Customer withdraw blocked when platform float low** → Mitigation: clear error code; admin deposit path; document in frontend wallet/admin docs.
- **[Risk] Dashboard “income” mixes funding and operating deposits** → Mitigation: type filters + docs; dedicated counters.
- **[Risk] Meal rows disappear from Admin Wallet history** → Mitigation: document; meal revenue from delivery/payment queries; future paired recognition rows if UI needs them in the same table.
- **[Risk] Import cycles wallet ↔ admin_wallet** → Mitigation: lazy import inside atomic helpers (existing meal pattern).

## Migration Plan

1. Add types + counters migration; extend ingestion services.
2. Hook recharge/withdraw; disable meal cash credit call site.
3. Adjust dashboard query semantics + serializers if new counter fields exposed.
4. Ship reconcile command; update tests/docs/OpenAPI descriptions.
5. Deploy with funding flag on; verify recharge → Admin Wallet balance in staging.
6. Rollback: set `ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED=False` and restore meal cash credit call if urgently needed (document as emergency only).

## Open Questions

- Should historical meal `customer_payment` cash credits be reversed/netted when backfilling funding, or left forever with a cutover note?
- Should Admin Panel transaction history include meal revenue rows (net-zero recognition) in this change, or only cash custody + separate meal-revenue metric?
- Exact HTTP mapping for withdraw blocked by Admin Wallet float (`409` vs `422`) — prefer `409` Conflict / insufficient platform float.
