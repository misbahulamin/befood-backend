# Admin Profit — Frontend Integration

## Summary

Admin Panel **Profit** analytics from an immutable meal profit ledger. Totals are **read from saved rows** — the API does not rescan all deliveries on each request.

**Base URL:** `/api/v1/web/admin-profit/`  
**Auth:** verified admin (`Authorization: Token …` or JWT as used by Admin Panel)  
**Client:** web admin only

### Migration from Wallet dashboard (BREAKING)

These fields were **removed** from `GET /api/v1/web/admin-wallet/dashboard/`:

| Removed wallet field | Use instead |
|----------------------|-------------|
| `total_profit` | `lifetime_profit` on Admin Profit dashboard |
| `month_profit` | `month_profit` on Admin Profit dashboard |
| `profit_by_package` | `profit_by_package` on Admin Profit dashboard (flat list for the active range) |

Wallet dashboard remains cash/custody only. See [`admin-wallet.md`](./admin-wallet.md).

## Recommended call order

1. `GET /dashboard/` — cards + package / meal-period / customer breakdowns + daily chart
2. Optional filters on dashboard: `start_date`, `end_date`, `package`, `customer`, `meal_period`
3. `GET /history/?…` — paginated ledger rows for drill-down tables

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| Profit home / cards / charts | GET | `/api/v1/web/admin-profit/dashboard/` |
| Ledger history table | GET | `/api/v1/web/admin-profit/history/` |

## Dashboard response

```json
{
  "lifetime_profit": "50000.00",
  "month_profit": "12000.00",
  "today_profit": "800.00",
  "range_start": "2026-09-01",
  "range_end": "2026-09-30",
  "range_profit": "12000.00",
  "range_revenue": "52000.00",
  "range_food_cost": "38000.00",
  "range_deliveries": 800,
  "profit_by_package": [
    {
      "package_public_id": "uuid",
      "package_name": "Student Package",
      "charged_deliveries": 500,
      "revenue": "26000.00",
      "food_cost": "19000.00",
      "profit": "7000.00"
    }
  ],
  "profit_by_meal_period": [
    {
      "meal_period": "lunch",
      "charged_deliveries": 400,
      "revenue": "30000.00",
      "food_cost": "22000.00",
      "profit": "8000.00",
      "profit_share_percent": "66.67"
    }
  ],
  "profit_by_customer": [
    {
      "customer_public_id": "uuid",
      "customer_email": "a@example.com",
      "charged_deliveries": 100,
      "revenue": "6000.00",
      "food_cost": "4500.00",
      "profit": "1500.00"
    }
  ],
  "daily_profit_chart": [
    {
      "date": "2026-09-01",
      "profit": "500.00",
      "revenue": "2000.00",
      "food_cost": "1500.00",
      "charged_deliveries": 40
    }
  ]
}
```

### Field meanings

| Field | Meaning |
|-------|---------|
| `lifetime_profit` | Sum of all ledger `profit_amount` (optionally scoped by package/customer/meal_period filters) |
| `month_profit` | Current calendar month by **`service_date`** |
| `today_profit` | Today by **`service_date`** (project timezone) |
| `range_*` | Aggregates for `start_date`–`end_date` window (defaults to current month) |
| `profit_by_package` | Package rows in the active range |
| `profit_by_meal_period` | Lunch vs dinner in the active range (+ share %) |
| `profit_by_customer` | Top customers by profit in the active range |
| `daily_profit_chart` | Daily series for graphs (`date` ascending) |

### Dashboard query params

| Param | Example | Notes |
|-------|---------|-------|
| `start_date` / `end_date` | `2026-09-01` | Inclusive `service_date`; drives range breakdowns + chart |
| `package` | meal package `public_id` | Scopes all aggregates |
| `customer` | customer `public_id` | Scopes all aggregates |
| `meal_period` | `lunch` \| `dinner` | Scopes all aggregates |

Yearly profit: set `start_date=2026-01-01` & `end_date=2026-12-31` and read `range_profit`.

## History

```http
GET /api/v1/web/admin-profit/history/?start_date=2026-09-01&end_date=2026-09-13&meal_period=lunch
```

Allowlisted filters only (`start_date`, `end_date`, `package`, `customer`, `meal_period`, `page`, `page_size`). Others → **400**.

Paginated (`results`, `count`, …). Each row includes `public_id`, delivery/customer/package ids, `meal_period`, `service_date`, `meal_price`, `food_cost`, `operational_cost`, `profit_amount`, `profit_percentage`, `source`, timestamps.

## Suggested UI

1. Cards: Lifetime / This Month / Today from top-level fields.
2. Date range picker → pass `start_date`/`end_date`; bind charts to `daily_profit_chart` and tables to package/customer/meal-period arrays.
3. History page for row-level audit with the same filters.
4. Never show Wallet `month_revenue` as profit.

## Errors

| Status | When |
|--------|------|
| `401` | Missing/invalid auth |
| `403` | Not verified admin |
| `400` | Bad date or unsupported filter |
