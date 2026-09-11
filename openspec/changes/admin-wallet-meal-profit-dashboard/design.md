## Context

Admin Panel `/admin/wallet` loads one endpoint today: `GET /api/v1/web/admin-wallet/dashboard/`. That payload mixes **cash custody** (funding credits, withdrawals, expenses) with lifetime meal **revenue** (`total_customer_payments` = Σ charged `OrderDelivery.charged_amount`). It does **not** expose realized meal **profit**.

Profit is already defined at meal costing time:

- `MealCyclePlan.profit_percent` drives planned margin.
- On menu publish, each `MonthlyMenuSlot` stores `profit_snapshot`, `ingredient_cost_snapshot`, `operational_cost_snapshot`, and `final_meal_price_snapshot`.
- Delivery charges debit the customer wallet using the published slot final price; Admin Wallet cash is **not** re-credited at meal time.

Stakeholders: platform admins (P&L cards on Wallet page), Admin Panel frontend, backend Admin Wallet / meals / orders teams.

Constraints: keep existing dashboard fields stable (additive only); money as decimal strings; verified-admin auth unchanged; prefer one response so the page does not need a second round-trip for v1.

## Goals / Non-Goals

**Goals:**

- Expose `total_profit` (lifetime) and `month_profit` (current calendar month in project timezone) on the dashboard.
- Expose package-wise breakdown for drill-down: which meal package contributed how much profit (and supporting delivery count / revenue).
- Base profit on charged deliveries × published slot `profit_snapshot` (same lock used for selling price).
- Document frontend UX: two clickable profit cards → package breakdown view.
- Keep cash metrics (`month_revenue` = Admin Wallet credit income) clearly distinct from meal profit.

**Non-Goals:**

- Changing how `profit_percent` or slot snapshots are computed/published.
- Crediting Admin Wallet cash when meals are delivered.
- Full P&L (inventory COGS variance, Onahar, referral commission netting) on this page.
- Instant-meal-only profit paths beyond what shares the same charged-delivery + slot snapshot model.
- Denormalizing profit onto `OrderDelivery` in v1 (optional later if aggregation is slow).
- Building the Admin Panel UI in this backend repo (docs + API contract only).

## Decisions

### 1. Extend existing dashboard endpoint (not a new route)

- **Choice:** Add profit fields to `dashboard_payload()` / `AdminWalletDashboardSerializer`.
- **Why:** Frontend already uses a single dashboard call; user wants cards on the same page with click → breakdown from that data.
- **Alternatives:** Separate `GET .../profit/` or `GET .../profit-by-package/` — cleaner for large lists/pagination, but extra round-trips and diverges from current UX. Revisit if package count or history volume becomes large.

### 2. Realized profit = charged delivery × published slot `profit_snapshot`

- **Choice:** For each `OrderDelivery` with `payment_status=charged` and non-null `charged_amount`, resolve meal package via order/subscription meal, resolve published slot for `(meal, service_date, meal_period)`, sum `profit_snapshot` (treat null/missing as `0.00` and exclude from “matched” counts or track as unmatched — see below).
- **Why:** Matches locked publish-time margin; survives later catalog price changes; aligns with `meal-slot-final-price`.
- **Alternatives rejected:**
  - Recompute from live ingredient prices → breaks immutability.
  - Use plan `snapshot_profit` / expected servings → ignores per-slot menu variance.
  - Infer from Admin Wallet `month_revenue` → that is cash funding, not meal margin.

### 3. Month boundary aligned with existing revenue recognition time axis

- **Choice:** Filter month (and optional today) profit using the same timestamp axis as `meal_revenue_recognized`: `OrderDelivery.updated_at` within `_period_bounds_month()` / today bounds (project timezone already used by admin wallet queries).
- **Why:** Consistency with how period meal revenue is already computed in `queries.py`.
- **Alternative:** `service_date` calendar month — better “meals served in September” semantics, but would diverge from revenue recognition and confuse card pairing. Document clearly; can add `recognition=service_date|charged_at` later if product asks.

### 4. Package breakdown shape (inline on dashboard)

```json
"total_profit": "1234.56",
"month_profit": "210.00",
"profit_by_package": {
  "lifetime": [
    {
      "package_public_id": "...",
      "package_name": "Student",
      "charged_deliveries": 40,
      "revenue": "2400.00",
      "profit": "320.00"
    }
  ],
  "month": [ /* same row shape, current month only */ ]
}
```

- **Choice:** Nested `lifetime` + `month` arrays so one click handler can choose the matching list for Total vs This Month cards without a second request.
- **Why:** Matches UX (“click box → that period’s package breakdown”).
- **Ordering:** Descending by `profit`, then `package_name` for stability.
- **Packages with zero profit in the period:** Omit empty packages from the list (totals still correct).

### 5. Missing snapshot / unmatched deliveries

- **Choice:** Include charged delivery in **revenue** sums via `charged_amount`; contribute `0.00` to profit when slot/`profit_snapshot` cannot be resolved; do not fail the dashboard. Optionally expose `unmatched_profit_deliveries` count later — not required for v1 UI.
- **Why:** Legacy or emergency charge paths must not 500 the wallet page.

### 6. Implementation placement

- **Choice:** Add `meal_profit_recognized(...)` and `meal_profit_by_package(...)` in `admin_wallet/services/queries.py` (or a thin `admin_wallet/services/profit.py` if queries grows too large). Reuse `resolve_published_slot_for_delivery` / `delivery_meal()` rather than duplicating join rules.
- **Aggregation approach for v1:** Efficient queryset joining where possible; acceptable Python aggregation with `select_related`/`prefetch` for correctness first. Add indexes / denormalized `profit_snapshot` on delivery only if profiling shows pain.

### 7. Frontend plan (docs-only in this change)

Document in `admin_wallet/docs/frontend/admin-wallet.md`:

1. Map `total_profit` / `month_profit` to two summary cards beside existing cash cards.
2. On card click, open modal/drawer listing `profit_by_package.lifetime` or `.month`.
3. Columns: package name, charged deliveries, revenue, profit (BDT decimal strings).
4. Do not reuse `month_revenue` for profit cards — that remains cash income.
5. Auth and base path unchanged (`IsVerifiedAdmin`, `/api/v1/web/admin-wallet/`).

## Risks / Trade-offs

- **[Risk] N+1 or heavy joins on large delivery history** → Mitigation: aggregate in SQL where feasible; limit breakdown fields; later denormalize profit at charge time.
- **[Risk] Operators confuse `month_revenue` (cash) with `month_profit` (margin)** → Mitigation: distinct field names + frontend docs + OpenAPI descriptions.
- **[Risk] Missing slots understate profit vs revenue** → Mitigation: document zero-profit contribution; optional unmatched counter in a follow-up.
- **[Risk] `updated_at` month ≠ service-month mental model** → Mitigation: document recognition rule; revisit if product prefers `service_date`.
- **[Trade-off] Inline breakdown vs dedicated endpoint** → Inline favors UX simplicity; dedicated endpoint later if payload grows.

## Migration Plan

1. Ship additive serializer fields (backward compatible).
2. No DB migration required for v1.
3. Deploy backend → update Admin Panel to show cards using new fields.
4. Rollback: ignore new fields on frontend; backend can leave fields (harmless) or revert serializer only.

## Open Questions

- None blocking for v1. Product may later request `service_date` recognition or net-of-referral profit — out of scope unless raised before apply.
