## Context

The `wallet` app is registered in `INSTALLED_APPS` but is an empty stub: no models, migrations, services, serializers, views, or URL mount. A broken unit test expects `Wallet` plus `credit_wallet` / `debit_wallet`. The `payments` app has generic `PaymentIntent` / webhook stubs but is also unmounted and not wired to wallets. Orders already mention wallet as a future payment concept in older migrations, but checkout-from-wallet is out of scope.

Stakeholders: authenticated customers (mobile/web) who need balance, history, recharge, and withdraw; operators who need Django admin audit; future payment-gateway work (bKash, Nagad) that must attach without rewriting the ledger.

Constraints:
- Follow project patterns: service layer in `wallet/services/`, thin DRF views, Token auth, `IsVerifiedCustomer` / customer ownership scoping, `PublicIdMixin` before mounting public routes.
- Money as `DecimalField` (project convention: `max_digits` + `decimal_places=2`), implicit BDT — document currency explicitly on the wallet.
- Mount under a domain prefix like existing apps (`/wallet/`), not invent a parallel `/api/v1/mobile/wallet` unless needed later.
- No live gateway SDKs in this change.

## Goals / Non-Goals

**Goals:**
- One wallet per `CustomerProfile` with a concurrency-safe balance.
- Append-only ledger (`WalletTransaction`) as the source of truth for every balance change.
- Customer APIs: get wallet, list/detail transactions, recharge (manual credit), withdraw (manual debit).
- Structure method/status/reference fields so gateway recharge/payout can complete pending intents later without schema rewrite.
- Admin visibility + tests + docs (UUID identity rules included).

**Non-Goals:**
- Integrating bKash, Nagad, SSLCommerz, or any live payment provider.
- Paying for orders from wallet / refunding orders into wallet (separate future change).
- Multi-currency wallets.
- Peer-to-peer transfers.
- Interest, cashback engines, or promotional credits as first-class products (ledger `type` may reserve `adjustment` for later admin use, but no customer adjustment API now).
- Replacing or mounting the existing `payments` CRUD stubs.

## Decisions

### 1. Domain ownership: wallet app owns balances; payments owns gateways later
- **Choice:** Implement balance + ledger + manual funding entirely in `wallet`. Future gateway confirmations call into `wallet.services` (credit/debit) from `payments` webhooks — do not couple recharge API to `PaymentIntent` in v1.
- **Rationale:** Keeps a clean ledger core; payments models today are order-centric and incomplete.
- **Alternatives considered:**
  - Route every recharge through `payments.PaymentIntent` now — premature; intents currently require an `Order` FK.
  - Put balance fields on `CustomerProfile` — weak audit trail and harder to freeze/lock independently.

### 2. Data model
- **Choice:**
  - `Wallet`: `OneToOneField(CustomerProfile)`, `balance` `DecimalField(12, 2)` default `0`, `currency` default `"BDT"`, `status` (`active` | `frozen`), `PublicIdMixin`, timestamps. Balance MUST only change via ledger service.
  - `WalletTransaction`: append-only row with `public_id`, FK to wallet, `type` (`recharge` | `withdraw` | reserved: `payment` | `refund` | `adjustment`), `direction` (`credit` | `debit`), positive `amount`, `balance_after`, `status` (`pending` | `completed` | `failed` | `cancelled`), `method` (`manual` | `bkash` | `nagad` | reserved others), optional `external_ref`, optional `idempotency_key` (unique per wallet when set), `note`, `metadata` JSON, timestamps. Completed money-moving rows are immutable (no amount/status downgrade via customer API).
- **Rationale:** Standard wallet ledger pattern; supports future pending→completed gateway flows; UUID-first for public APIs.
- **Alternatives considered:**
  - Signed amount only (no direction) — less clear for clients/reporting.
  - Update balance without ledger rows — fails audit and professional standard.

### 3. Concurrency and invariants
- **Choice:** All credit/debit paths use `transaction.atomic()` + `select_for_update()` on the wallet row; reject debit when `amount > balance`; reject ops when `status == frozen`; never allow negative balance; store `balance_after` on each completed entry.
- **Rationale:** Prevents race conditions on concurrent recharge/withdraw.
- **Alternatives considered:** Optimistic version field only — locking is simpler and sufficient at expected volume.

### 4. Manual recharge / withdraw behavior (v1)
- **Choice:** Customer `POST` recharge or withdraw with `{ "amount": "500.00", "note": "..." }` creates a **completed** ledger entry with `method=manual` and updates balance immediately (dev/manual funding path). Minimum amount `0.01`; maximum amount configurable constant (e.g. `100000.00`); amount must have at most 2 decimal places.
- **Rationale:** Matches product ask (“recharge 500 and it adds”); withdraw mirrors for symmetry until payout gateways exist.
- **Alternatives considered:**
  - Withdraw as admin-approved pending request only — safer for real cash-out, but user asked for normal withdraw now; keep `status`/`method` so approval/payout can be introduced later without breaking clients.
  - Always create `pending` then auto-complete — extra noise for manual path; prefer immediate `completed` for `method=manual`.

### 5. Gateway readiness (no integration yet)
- **Choice:** Document and reserve:
  - `method` values `bkash` / `nagad`
  - `status=pending` + `external_ref` for in-flight gateway sessions
  - Service entry points like `complete_pending_credit(txn)` / `fail_pending(txn)` for future webhook handlers
  - Do **not** expose customer APIs that accept `method=bkash` until providers are integrated (v1 request body does not choose gateway; server sets `manual`)
- **Rationale:** Avoid fake gateway success while keeping schema forward-compatible.
- **Alternatives considered:** Stub fake bkash success endpoints — encourages incorrect client integration.

### 6. API shape
- **Choice:** Mount `path('wallet/', include('wallet.api.urls'))` in `core/urls.py`:
  - `GET /wallet/` — caller's wallet summary (`public_id`, `balance`, `currency`, `status`); auto `get_or_create` wallet
  - `GET /wallet/transactions/` — paginated ledger for caller's wallet (newest first)
  - `GET /wallet/transactions/{public_id}/` — single transaction (ownership-scoped)
  - `POST /wallet/recharge/` — credit
  - `POST /wallet/withdraw/` — debit
- **Rationale:** Resource nouns + action sub-resources for funding ops (apiguide action pattern); matches project prefix style (`/orders/`, `/meals/`).
- **Alternatives considered:**
  - Full ViewSet CRUD on wallet — customers must not create/delete wallets arbitrarily.
  - Nest under `/user_management/` — wallet is its own bounded context.

### 7. Auth, BOLA, and public identity
- **Choice:** `IsVerifiedCustomer` on all customer wallet endpoints. Resolve wallet only via `request.user` → `customer_profile`. Transaction detail lookup by `public_id` **and** wallet ownership. Serializers expose `public_id`, never integer PK as client identity.
- **Rationale:** Matches orders/meals customer APIs and deferred-domain UUID spec.
- **Alternatives considered:** `HasCustomerProfile` only — prefer verified-customer consistency with meal purchase flows.

### 8. Idempotency
- **Choice:** Optional request header `Idempotency-Key` (or body field) stored on `WalletTransaction.idempotency_key` unique per wallet; replay returns the original completed result; same key + different amount → `409 Conflict`.
- **Rationale:** Mobile retries on flaky networks; critical for funding ops even before gateways.
- **Alternatives considered:** No idempotency — simpler but unsafe for double-credit on retry.

### 9. Wallet provisioning
- **Choice:** Lazy `get_or_create` on first wallet API access (and from funding endpoints). Optional post_save signal on `CustomerProfile` is nice-to-have but not required for correctness.
- **Rationale:** Avoids migration backfill complexity for existing customers; first call creates balance `0`.
- **Alternatives considered:** Data migration creating wallets for all customers — unnecessary until volume demands it.

### 10. Admin
- **Choice:** Register `Wallet` and `WalletTransaction` in Django admin with list/search/filters; balance and completed transaction amounts read-only in admin forms; discourage raw balance edits (document that corrections go through service/`adjustment` later).
- **Rationale:** Ops visibility without bypassing ledger invariants casually.

### 11. Docs & OpenAPI
- **Choice:** `extend_schema` on views; `wallet/docs/frontend/customer-wallet.md` and `wallet/docs/backend/customer-wallet.md` stating UUID identity, money format, manual vs future gateway, and that integer PKs are internal-only.
- **Rationale:** Project docs pattern + deferred-domain readiness checklist.

## Risks / Trade-offs

- **[Risk] Manual recharge/withdraw can be abused in production if left open** → Mitigation: document as temporary funding path; gate behind settings flag `WALLET_MANUAL_FUNDING_ENABLED` (default True in DEBUG / configurable); replace with gateway-only when ready.
- **[Risk] Immediate withdraw implies cash left the company books without payout rail** → Mitigation: v1 is ledger-only (balance decreases); real bank/MFS payout is a later payments change; product/ops must treat manual withdraw as internal balance reduction, not guaranteed cash transfer.
- **[Risk] Double-spend under concurrency** → Mitigation: `select_for_update` + atomic debit check.
- **[Risk] Clients hard-code `method=manual`** → Mitigation: omit client-supplied method in v1; server sets it; document reserved methods for future.
- **[Risk] Broken existing `wallet/tests/test_basic.py`** → Mitigation: replace/extend with real ledger tests in this change.

## Migration Plan

1. Implement models + initial migration (replace empty `0001_initial` if never applied; otherwise add `0002_...` — verify migration state at apply time).
2. Implement services, API, admin, URL mount, docs, tests.
3. Enable clients against `/wallet/` endpoints.
4. Rollback: unmount routes; keep tables (safe). Do not drop ledger history without an explicit later migration.

## Open Questions

- None blocking. Follow-ups: admin-approved withdraw payout workflow; order payment/refund via wallet; gateway pending→completed webhooks in `payments`.
