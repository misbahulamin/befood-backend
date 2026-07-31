## Context

Customers place meal packages via `POST /orders/` → `create_meal_order`. Today `calculate_order_period` always uses `timezone.localdate()`, so `order_month` is derived from “now” and cannot target a future meal month. `Order.order_month` (`YYYY-MM`) and the unique non-cancelled `(customer, order_month)` lock already exist. Published menus live on `MonthlyMenuSchedule` (`status=published`), looked up by `published_schedule_for_meal(meal_id, year, month)`. Wallet minimum and month-lock gates already run inside `create_meal_order` but against the server-derived month only.

Stakeholders: verified customers (mobile/web), meal ops admins who publish monthly schedules.

## Goals / Non-Goals

**Goals:**

- Let customers choose a meal month from **current month through +12 months** (13 options; default = current).
- Persist that choice as `order_month` and compute service dates/deliveries for the target month.
- Require a **published** monthly menu for the selected meal + month before confirm (and before showing order-time menu content).
- Provide a lean customer API for the month picker (labels + publish flags).
- Keep month-lock and wallet-min eligibility integrated against the **selected** month.
- Document the contract for frontend (implementation task; artifact under `orders/docs/frontend/` and/or `meals/docs/frontend/`).

**Non-Goals:**

- Ordering for **past** months.
- Changing admin publish/finalize workflows.
- Wallet debit / checkout payment.
- Allowing two non-cancelled packages in the same `order_month`.
- Changing `GET /meals/today-menu/` reveal rules.
- Replacing `GET /meals/my-package-menu/` ownership model for already-ordered packages.

## Decisions

### 1. Reuse `order_month`; accept client year/month on create

**Choice:** Add optional `year` + `month` (integers) to `OrderCreateSerializer`. When omitted, behave as today (current local month / today’s reference date). When present, validate both and set the target meal month.

**Rationale:** `order_month` and DB constraint already encode the product rule; no new column. Integer year/month match existing package-menu query style.

**Alternatives:** Single `order_month` string — rejected as less consistent with `my-package-menu`. New `meal_month` FK — unnecessary while `YYYY-MM` + cycle uniqueness already work.

### 2. Selectable window = current … +12 months

**Choice:** Allowed set is 13 calendar months starting at `(local_today.year, local_today.month)`. Reject anything outside with `400`/`422` validation error.

**Rationale:** Matches product example (e.g. July 2026 … June 2027).

### 3. Period calculation for a selected month

**Choice:** Extend `calculate_order_period` (or a thin wrapper) to accept an explicit target `(year, month)`:

- **Current month selected:** keep today’s behavior (`reference_date = localdate()`).
- **Future month selected:** use `reference_date = date(year, month, 1)` so monthly packages cover the full target calendar month; shorter meal types start from the 1st of that month.

`order_month` MUST equal `f"{year:04d}-{month:02d}"` for the selected target (not a different month derived from a multi-month meal type span). For `six_months` / `yearly` meal types, still stamp `order_month` as the **selected start month** and keep duration math from that reference; month-lock remains on that stamp (same as today).

**Alternatives:** Always use day-1 even for current month — would change mid-month daily/weekly starts; rejected to avoid breaking current-month behavior.

### 4. Publish gate before create

**Choice:** After resolving target month and before/alongside lock + wallet checks, call `published_schedule_for_meal(meal.id, year, month)`. If none, raise a dedicated domain error (e.g. `MenuNotPublishedError`) mapped to a clear customer message:

- EN: `This month's menu has not been published yet. Once the menu is published, you will be able to place your order.`
- (Clients may localize; API returns one stable English `detail`/`message` unless the project already returns Bangla elsewhere.)

**Rationale:** Prevents ordering into an empty/unpublished cycle. Reuses existing meals service.

### 5. Eligibility order (unchanged semantics, target-aware)

**Choice:** Inside `create_meal_order`:

1. Meal active + priced  
2. Target month in allowed window  
3. Published schedule for meal + month  
4. `check_existing_monthly_lock(customer, order_month)`  
5. `check_wallet_min_balance(customer)`  
6. Snapshot + create + deliveries  

**Note on product wording:** User copy sometimes reads as OR between “no active order” and “wallet above minimum.” Existing shipped rule is **AND** (month lock for that month **and** wallet minimum). This change **keeps AND**; “no previous active order” means no locking order for the **selected** meal month (other months remain allowed).

### 6. Orderable-months endpoint

**Choice:** `GET /api/v1/orders/orderable-months/?meal_public_id=<uuid>` (verified customer).

Response items (lean, mobile-friendly):

| Field | Meaning |
| --- | --- |
| `year`, `month` | Calendar identifiers |
| `order_month` | `YYYY-MM` |
| `label` | e.g. `July 2026` (English month name; clients may reformat) |
| `is_current` | Default selection hint |
| `is_published` | Published schedule exists for this meal + month |
| `has_order` | Caller already has a non-cancelled order for this `order_month` |

**Rationale:** One round-trip for the picker; publish + lock state without creating an order. Placed under orders because it is order-flow UX; meals publish lookup stays in meals services.

**Alternatives:** Pure client-side month list + separate publish check — more chatter and inconsistent labels.

### 7. Pre-order menu preview (modify package-menu capability)

**Choice:** Add `GET /api/v1/meals/order-menu-preview/?meal_public_id=&year=&month=` for verified customers. Returns the same slot/ingredient shape as package menu for that meal when published; if unpublished, `200` with `schedule_published: false` and empty days **or** `422` with the not-published message — prefer **`200` + `schedule_published: false`** for picker UX (show message without treating as hard error), while **order create** hard-rejects unpublished.

Does **not** require an existing order. Does **not** expose other customers’ data (keyed by public meal id + publish status only).

**Rationale:** `my-package-menu` stays ownership-scoped for post-order calendar; preview is explicitly order-flow.

### 8. Docs after implement

**Choice:** Frontend guide at `orders/docs/frontend/future-month-meal-ordering.md` (workflow: list months → preview menu → create with year/month → errors). Cross-link meals preview if needed. Matches existing `orders/docs/frontend/order-eligibility-wallet-min-balance.md` style.

## Risks / Trade-offs

- **[Risk] Mid-month order for “current” monthly package still covers full calendar month** → Already true today; document clearly so users understand selecting July on 31 Jul still means July package.
- **[Risk] Future daily/weekly packages start on day 1 of selected month** → Acceptable; document. Ops may prefer monthly packages for advance orders.
- **[Risk] Price snapshot uses meal’s current `total_price`, which may be from a different finalized cycle** → Existing behavior; mitigate later by binding price to target cycle if product requires it (out of scope).
- **[Risk] Race: two creates same month** → Existing unique constraint + service check; keep both.
- **[Risk] Unpublished → published after picker load** → Client should re-check on confirm; server enforces on create.
- **[Trade-off] AND eligibility vs OR wording** → Keep AND for consistency with wallet-min change; document in frontend guide.

## Migration Plan

1. Deploy backend (no destructive migration if only code/API; `order_month` already exists).
2. Clients adopt month picker + send `year`/`month`; old clients omitting fields keep current-month behavior (**backward compatible**).
3. Rollback: ignore new query/body fields; remove new endpoints — old create path remains.

## Open Questions

- None blocking: Bangla message can be client-side if API stays English-only to match existing order errors.
- Confirm whether `six_months` / `yearly` packages should be restricted to current-month-only in a follow-up; for now allow with start-month stamp as above.
