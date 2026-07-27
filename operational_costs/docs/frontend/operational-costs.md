# Frontend — Per-Month Operational Costs

Backend overview: [`../backend/overview.md`](../backend/overview.md).

## BREAKING changes

| Before (removed) | After |
|------------------|--------|
| Global lines + immutable amount history | Month-scoped entries (`year` + `month`) |
| `PUT/PATCH .../amount/` (versioning) | `PATCH .../{public_id}/` with `amount` (overwrite) |
| `GET .../history/` | Removed (404) |
| `GET /operational-costs/` without period | **Requires** `?year=&month=` |
| `amount_effective_from` on responses | Removed |
| Seeded global Rent / Cook / Helper / Utilities | No global seed; add rows per month |

Also still true from the app extract: base path is `/operational-costs/` (not `/meals/operational-costs/`).

## What to build

1. **Cost settings screen** — pick calendar month (e.g. January 2027) → list/add/edit that month’s rows (salary, home rent, …); overwrite amounts in place; toggle `is_active`.
2. **Plan summary / finalize UI** — show allocated `operational_cost`, kitchen `operational_cost_total`, and entry breakdown from meals cycle-plan summary (uses the **cycle’s** year/month).

## Auth

```http
Authorization: Token <admin_token>
```

Verified admin only (`IsVerifiedAdmin`).

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| Load month | GET | `/operational-costs/?year=2027&month=1` |
| Add entry | POST | `/operational-costs/` |
| Detail | GET | `/operational-costs/{public_id}/` |
| Update amount / metadata | PATCH | `/operational-costs/{public_id}/` |
| Plan costing (meals) | GET | `/meals/cycle-plans/{public_id}/summary/` |

Money fields are **decimal strings** (e.g. `"15000.00"`).

## Request / response examples (January 2027)

### Create entries

`POST /operational-costs/`

```json
{
  "year": 2027,
  "month": 1,
  "name": "Salary",
  "amount": "20000.00",
  "sort_order": 10
}
```

```json
{
  "year": 2027,
  "month": 1,
  "name": "Home rent",
  "amount": "15000.00",
  "sort_order": 20
}
```

### List that month

`GET /operational-costs/?year=2027&month=1`

Returns only January 2027 entries. Omitting `year` or `month` returns **400**.

### Overwrite amount in place

`PATCH /operational-costs/{public_id}/`

```json
{
  "amount": "16000.00",
  "notes": "landlord increase"
}
```

No history rows are created. `year` / `month` cannot be changed via update.

### Entry response (list/detail)

```json
{
  "id": 1,
  "public_id": "…",
  "year": 2027,
  "month": 1,
  "name": "Home rent",
  "slug": "home-rent",
  "is_active": true,
  "sort_order": 20,
  "notes": "landlord increase",
  "amount": "16000.00",
  "created_at": "2027-01-05T10:00:00Z",
  "updated_at": "2027-01-10T11:00:00Z"
}
```

## Suggested UI flow

1. Open **Operational costs** → select **January 2027** (or any month).
2. `GET /operational-costs/?year=2027&month=1`.
3. Add salary / rent / utilities with POST (include `year` + `month`).
4. Edit amounts with PATCH on the entry (not a separate amount URL).
5. On cycle plan summary for a January 2027 cycle, display product / other% / ops / profit; kitchen total is that month’s sum.

## Edge cases

- Inactive entries (`is_active=false`) are excluded from kitchen totals and from summary `operational_cost_lines`.
- February 2027 with no entries → kitchen total `0.00`; January totals stay unchanged.
- Adding a second package plan in the same cycle changes allocation shares for **draft** summaries.
- Finalized plans keep `snapshot_operational_cost` until reopen.
- Former `/history/` and `/amount/` paths return 404.
