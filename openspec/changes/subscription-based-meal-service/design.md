## Context

BeFood already runs a full **month-bounded meal package** stack in `orders/`:

- Customer `POST` creates an `Order` for a selected `order_month` (`YYYY-MM`).
- Unique constraint: one non-cancelled order per customer per month.
- Create generates all `OrderDelivery` slots for that month (e.g. 60/62 for `both`).
- Wallet eligibility (`OrderWalletSettings.min_wallet_balance_to_order`) is a **check only** at create; wallet is debited later when a slot is marked `delivered`.
- Meal-off, admin mark-delivered, kitchen demand, and package menus all hang off `Order` + `OrderDelivery`.

`meals.MealCategory` is already the Student / Regular / Premium (and future) **package** used by menu schedules, cycles, and pricing. `meal_type` (`daily` / `weekly` / `half_monthly` / `monthly` / …) encodes a **purchase duration**, which is the wrong commercial model for bachelor mess service.

Stakeholders: verified customers (subscribe once, eat until cancel), verified admins (plan catalog + subscriber ops + deliveries), kitchen (demand still from slots).

Constraints: services layer owns workflows; `PublicIdMixin` on new public resources; `IsVerifiedAdmin` for admin APIs; no silent debit at subscribe; do not rewrite meal-cycle costing or menu authoring.

## Goals / Non-Goals

**Goals:**

- Replace customer monthly repurchase with an **open-ended subscription** to one meal package.
- Let verified admins create and manage subscription plans (existing packages + new ones) with enough fields to add a package without a deploy.
- Gate subscribe on configured **minimum wallet balance** (same singleton pattern as today); do not charge at subscribe.
- Keep meals flowing: rolling delivery slots, meal-off, delivered debit, kitchen demand.
- Remove customer month picker / `year`+`month` order create / same-month lock as the purchase path.
- Document customer and admin frontend contracts.

**Non-Goals:**

- Netflix-style **monthly invoice capture** via a payment gateway (wallet remains prepaid; per-meal debit on delivery).
- Auto-pause or auto-cancel when balance later falls below the minimum (failed delivery debit already blocks that slot).
- In-place **plan switch** as a single atomic product (v1 = cancel, then subscribe to another plan).
- Reworking meal cycle costing, menu schedule authoring, or inventory deduction.
- Keeping daily/weekly/half-monthly **customer purchase** as a parallel checkout (those types stay out of the subscribe catalog).
- Deleting historical `Order` rows.

## Decisions

### 1. MealCategory is the subscription plan catalog

**Choice:** Do **not** add a parallel `SubscriptionPlan` table. `MealCategory` remains the commercial + kitchen package. Add `is_subscribable` (boolean, default `false` for duration types; `true` for ongoing plans such as Student/Regular/Premium). Customer subscribe catalog = `is_active` AND `is_subscribable`. Admin creates/updates plans through a dedicated verified-admin **subscription-plans** API that reads/writes `MealCategory` (same `public_id`), so the admin frontend has a Subscription section without duplicating kitchen identity.

**Why:** Packages, menus, cycles, demand grouping, and thumbnails already key off `MealCategory`. A second catalog would split Student/Regular/Premium into two public ids and drift.

**Alternatives:** New `SubscriptionPlan` FK → `MealCategory` — rejected for v1 (duplicate names/thumbnails, two ids). Rename `MealCategory` — rejected (too invasive).

**Config stored on the plan (MealCategory):** `meal_name`, `description`, `meal_thumbnail`, `meal_period` (`lunch` | `dinner` | `both`), `is_active`, `is_subscribable`, existing published `total_price` for display. `meal_type` is **not** used to bound subscription length.

### 2. CustomerSubscription is the commercial entitlement

**Choice:** New `CustomerSubscription` (`PublicIdMixin`) in `orders/`:

| Field | Role |
|-------|------|
| `customer` | Owner |
| `meal` | FK `MealCategory` (plan) |
| snapshots | `meal_name_snapshot`, `meal_period_snapshot` at subscribe time |
| `status` | `active` \| `cancelled` |
| `started_on` | Local business date (meal-off timezone) when service starts |
| `cancelled_at` / `cancel_effective_on` | When the customer cancelled; last date slots may still be served |
| timestamps | `created_at`, `updated_at` |

Constraint: **at most one `active` subscription per customer**.

Subscribe does **not** create a month-bounded `Order`. Historical monthly orders remain for past service.

**Why:** Matches “subscribe once, cancel to stop.” Snapshots keep kitchen/customer display stable if admin later edits the plan name/period.

**Alternatives:** Reuse `Order` with a null `order_end_date` — rejected (month lock, completion-by-quota, and `order_month` are the old model). Create a hidden `Order` every month — rejected (still the monthly order system).

### 3. Deliveries attach to the subscription; Order FK becomes historical

**Choice:** Add nullable `subscription` FK on `OrderDelivery`. New slots set `subscription_id` and leave `order_id` null. Historical rows keep `order_id`. Unique slot key becomes `(subscription, service_date, meal_period)` for new rows (legacy unique on order remains for old rows).

Meal-off, mark-delivered, and wallet debit continue to operate on `OrderDelivery`. Kitchen demand counts deliveries whose parent **active subscription** (or, for unmigrated history, non-cancelled order) matches the date/period.

**Why:** Smallest change to the operational unit kitchen already uses.

**Alternatives:** New `SubscriptionDelivery` table — rejected (duplicate mark-delivered/payment/meal-off). Keep generating monthly `Order` rows internally — rejected by product.

### 4. Rolling slot generation, not a closed month quota

**Choice:** A domain service `ensure_subscription_deliveries(subscription, through_date)` creates missing `scheduled` slots for each service date in `[started_on, through_date]` according to `meal_period_snapshot`, **only where** a published `MonthlyMenuSchedule` exists for that plan and calendar month.

Horizon: **today (Asia/Dhaka) through the last day of next calendar month** (two-month window). Invoke on:

- successful subscribe
- daily management command (ops cron)
- admin/customer reads that need upcoming slots (idempotent ensure)

If a month is unpublished: skip those dates; subscription stays `active`; slots appear when the menu is published and ensure runs again.

Do **not** pre-generate a year of rows. Do **not** complete/cancel the subscription when a month’s slots become terminal.

**Why:** Kitchen still plans by month; customers never re-confirm; unpublished future months do not block subscribe.

**Alternatives:** Generate 12 months at subscribe — rejected (row explosion, unpublished menus). Lazy-create only “today” — rejected (meal-off for tomorrow and demand boards need upcoming rows).

### 5. Wallet gate at subscribe (no debit)

**Choice:** Reuse `OrderWalletSettings` singleton. Semantics: `min_wallet_balance_to_order` is the **minimum balance to subscribe**. Expose it to customers as today (wallet payload) and in subscribe error copy. Checks:

1. Wallet missing → treat as `0`
2. `status=frozen` → reject
3. `balance < minimum` → reject
4. Else subscribe; **no ledger write**

Per-meal debit on `delivered` is unchanged (`meal-delivery-wallet-payment`).

**Why:** Same admin control and prepaid-fund intent; only the gated action changes.

**Alternatives:** Debit a month of estimated meals at subscribe — rejected (product said check only). Per-plan minimums — deferred; one global threshold is what admins already configure.

### 6. Cancel stops future service; today follows meal-off rules

**Choice:** Customer `POST .../cancel/` on their active subscription:

- Set `status=cancelled`, `cancelled_at=now`, `cancel_effective_on=today` (settings timezone).
- Leave slots with `service_date <= today` as-is (meal-off deadlines still apply for remaining today periods).
- Mark `scheduled` slots with `service_date > today` as `skipped` with a dedicated skip source (`system` / subscription-cancel) so demand drops and nothing is cooked.
- Do not delete rows (audit).

Admin may cancel with the same slot rules.

**Why:** Kitchen may already be committed to today’s remaining period; Netflix-style “end of period” is the calendar day, not a prepaid month.

**Alternatives:** Immediate skip of all remaining today slots — harsher on kitchen. Continue until end of calendar month — reintroduces monthly billing semantics the product wants to leave.

### 7. Remove customer monthly order create

**Choice:** Customer `POST` meal-order create **rejects** with a stable validation/conflict error pointing at subscribe (`error_code` documented). Do not accept `year`/`month` to start service. Orderable-months and future-month create are **retired** as purchase APIs (404/410 or the same migrate error — pick one in implementation and document it; prefer **410 Gone** or **409** with `SUBSCRIBE_REQUIRED` if the route stays mounted).

Keep:

- Customer list/detail of **historical** orders (read-only)
- Admin delivery mark endpoints
- Meal-off/on against subscription-owned slots (new or adapted URLs)

Current-package / “my active meal” MUST return the **active subscription**, not “non-cancelled order for `YYYY-MM`”.

**Why:** Clients cannot accidentally keep the old loop.

### 8. API surface (multi-client)

**Customer (JWT, verified):** lean payloads.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/subscription-plans/` | Active subscribable plans |
| POST | `/api/v1/subscriptions/` | Subscribe (`plan_public_id`) |
| GET | `/api/v1/subscriptions/current/` | Active subscription or null |
| POST | `/api/v1/subscriptions/current/cancel/` | Cancel |
| GET | `/api/v1/subscriptions/{public_id}/` | Own subscription detail + upcoming progress |

Meal-off stays period+date scoped but authorized via subscription ownership (existing meal-off routes may keep `/orders/` prefix if they already key by delivery `public_id`; ownership check uses subscription).

**Admin web (`IsVerifiedAdmin`):**

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/api/v1/web/subscription-plans/` | List/create plans |
| GET/PATCH | `/api/v1/web/subscription-plans/{public_id}/` | Update (including `is_subscribable`, `is_active`) |
| GET | `/api/v1/web/subscriptions/` | Paginated subscribers; filters: `status`, plan, dates |
| GET | `/api/v1/web/subscriptions/{public_id}/` | Detail + delivery progress |
| GET/PATCH | existing order-wallet settings | Minimum balance to subscribe |

Mark-delivered remains on existing web order-delivery routes, extended to load slots by `subscription_id`.

### 9. Permissions and identifiers

- Never trust client-supplied `customer_id` for subscribe/cancel.
- Lookup by `public_id` only on public/customer routes.
- Object-level: customer sees only own subscriptions; admin sees all.

### 10. Data migration of in-flight monthly orders

**Choice:** One-off data migration (RunPython):

1. For each customer with a non-cancelled `Order` whose `order_end_date >= today` (or `order_status` in `confirmed`/`active`), pick the **latest** such order by `order_start_date`.
2. Create `CustomerSubscription(status=active, meal=order.meal, snapshots from order, started_on=min(today, order_start_date))`.
3. Set `subscription_id` on that order’s still-`scheduled` (and other non-terminal) deliveries from `today` forward.
4. Other future-month non-cancelled orders for the same customer: cancel the `Order`, skip remaining `scheduled` slots (replaced by rolling generation on the new subscription).
5. Completed past orders: untouched.

Idempotent: skip customers who already have an active `CustomerSubscription`.

**Why:** Nobody in an active mess month should be asked to “order again” after deploy.

## Risks / Trade-offs

- **[Unpublished next month]** → Subscribers have no slots until admin publishes; demand is zero for that month. Mitigation: ensure job after publish; admin docs; customer status shows `menu_unpublished` for that month without cancelling the subscription.
- **[Unique constraint on OrderDelivery]** → Nullable `order` + new subscription unique needs a careful migration (partial unique constraints). Mitigation: PostgreSQL-style conditional uniques; if SQLite in tests, match existing project test DB constraints.
- **[Kitchen queries still filter on Order]** → Miss new slots. Mitigation: single demand service path updated in this change; tests with subscription-only deliveries.
- **[Clients still POST /orders/]** → **BREAKING**. Mitigation: documented error, frontend docs, keep history GET.
- **[Two active sources during rollout]** → Migration must run before customer traffic; dual-read in demand (subscription OR legacy order) until backfill completes.
- **[Low wallet after subscribe]** → Meals fail at mark-delivered. Mitigation: out of scope to auto-cancel; customer wallet UX already shows balance vs minimum.

## Migration Plan

1. Ship models + `is_subscribable` + nullable delivery FK + constraints.
2. Run data migration (in-flight orders → subscriptions).
3. Deploy APIs; turn off customer order create.
4. Point customer app at subscribe/cancel/current; admin at plan CRUD + subscriber list.
5. Enable daily `ensure_subscription_deliveries` cron.
6. Rollback: feature-flag subscribe vs order create only if shipped behind a flag; after create is removed, rollback is a revert deploy plus do not delete new subscription rows.

## Open Questions

- None blocking v1. Plan-change (switch without cancel) and auto-pause on low balance are deferred product decisions.
