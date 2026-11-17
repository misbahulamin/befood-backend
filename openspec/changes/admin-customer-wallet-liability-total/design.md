# Design

## Context

See `proposal.md` for motivation. Today Admin Wallet summary/dashboard (`admin_wallet/services/queries.py`) already exposes custody counters and `net_customer_funding = max(0, total_customer_funding - total_customer_withdrawals)`. That counter does **not** fall when customers spend wallets on meals. Customer spendable credit lives on `wallet.Wallet.balance` (`= recharge_balance + commission_balance`). The Admin Panel `/admin/wallet` overview already consumes `GET /api/v1/web/admin-wallet/dashboard/` via `useAdminWalletDashboard`.

## Goals / Non-Goals

**Goals:**

- Compute a live aggregate of customer prepaid liability from customer wallet rows.
- Expose it additively on existing Admin Wallet summary + dashboard JSON (same auth).
- Render one overview card on `/admin/wallet` and document field semantics vs `net_customer_funding`.

**Non-Goals:**

- Changing how funding custody or meal revenue is posted.
- Replacing or redefining `net_customer_funding`.
- Per-customer liability list, charts, or filters in this change.
- Splitting recharge vs commission into separate admin cards (v1 uses total `balance`).
- Caching/materialized counters unless a real performance issue appears.

## Decisions

### 1. Field name: `total_customer_wallet_balance`

- **Choice:** Add `total_customer_wallet_balance` (decimal string / Decimal, 2 places) on both `wallet_summary()` nested `wallet` object and top-level dashboard payload (mirror how funding fields are duplicated today).
- **Why:** Explicit “sum of wallet balances”; avoids conflating with `net_customer_funding`.
- **Alternatives:** `prepaid_liability`, `customer_wallet_liability` — clearer business language but less tied to the source field; can be the UI label while the API stays balance-oriented.

### 2. Definition: `SUM(Wallet.balance)` over all customer wallets

- **Choice:** Aggregate `wallet.Wallet` with `Sum('balance')`, defaulting null to `0.00`. Include `active` and `frozen` wallets.
- **Why:** Matches user intent (money still credited to customers / not yet spent). Frozen wallets still hold liability. `balance` already enforces the dual-bucket invariant.
- **Alternatives considered:**
  - Reuse `net_customer_funding` — rejected; ignores meal spend.
  - `SUM(recharge_balance)` only — rejects commission prepaid that can still buy meals.
  - Reconstruct from ledger transactions — slower and duplicates source of truth already on `Wallet.balance`.

### 3. Extend existing endpoints, no new route

- **Choice:** Compute inside `wallet_summary()` / `dashboard_payload()`; serializers + OpenAPI only.
- **Why:** Frontend already loads the dashboard once for overview cards; additive field avoids an extra round-trip.
- **Alternative:** Dedicated `GET .../customer-wallet-liability/` — unnecessary for a single scalar.

### 4. Frontend in befood-frontend

- **Choice:** After backend ships the field, update `AdminWalletPage` overview with a card (label e.g. “Customer wallet balances” / “Prepaid customer liability”), extend `adminWalletTypes.ts`, and tighten help copy so operators do not confuse it with Net customer funding.
- **Why:** `/admin/wallet` already maps dashboard fields to `AdminStatCard`s; pattern is established.
- **Note:** OpenSpec lives in befood-backend; frontend implementation is a sibling-repo task called out in `tasks.md`.

### 5. Docs

- Update `admin_wallet/docs/frontend/admin-wallet.md` (required by spec) and a short note in backend Admin Wallet docs describing the aggregate query and difference from custody net funding.

## Risks / Trade-offs

- **[Risk] Operators confuse new card with Net customer funding** → Mitigation: distinct label + help text; docs MUST contrast the two.
- **[Risk] Full-table `SUM` latency as wallet count grows** → Mitigation: single indexed aggregate on one numeric column; revisit denormalized counter only if needed.
- **[Risk] Dual-bucket invariant drift makes `balance` disagree with recharge+commission** → Mitigation: existing ledger invariant checks; aggregate uses `balance` as customer-facing total.
- **[Trade-off] Including commission** means liability includes non-withdrawable referral credit → Acceptable for “unconsumed meal credit”; document in frontend help.

## Migration Plan

1. Ship backend additive fields + tests (backward compatible).
2. Deploy backend; old frontends ignore unknown fields.
3. Ship frontend card + types + docs.
4. Rollback: remove/hide card on frontend; backend field can remain unused.

## Open Questions

- None blocking; UI label wording can be finalized at apply time (“Customer wallet balances” vs “Prepaid liability”) without changing the API field name.
