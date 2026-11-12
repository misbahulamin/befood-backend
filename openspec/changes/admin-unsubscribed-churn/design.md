# Design

## Context

See `proposal.md` for motivation. Today:

- `CustomerSubscription` already has `status`, `cancelled_at`, `cancel_effective_on`, `cancel_source`, `cancelled_by` (user FK). `cancel_subscription()` accepts `reason` but ignores it.
- Admin customers live in `user_management` (`admin_customer.py` allowlisted filters; `inactive_subscription` ≈ unsubscribed).
- Dashboard KPIs are built in `user_management/services/admin_dashboard.py`.
- Low-balance silent churn is a **current** flag (`meal_service_blocked_low_balance` + `meal_service_blocked_at`), not a per-day history table. Meal-offs are `OrderDelivery` skips with `skip_source` customer/admin.
- CSV export pattern exists (e.g. referrals commissions). Charts/admin UI are frontend-only.
- In-flight `admin-subscription-cancellation` owns cancel cutoffs/audit; this change owns reason persistence + lifecycle analytics.

## Goals / Non-Goals

**Goals:**

- One shared lifecycle module used by customers list, churn list, analytics, and dashboard.
- Required structured cancel reasons without breaking cancel slot/wallet semantics.
- Set-based filters (Exists/annotations); indexes for cancel dates/status.
- Additive dashboard fields and `/api/v1/web/churn/*` routes.

**Non-Goals:**

- Mobile cancel UI (API break still applies).
- Automated win-back messaging / CRM sync.
- Replacing `inactive_subscription` filter (keep; document overlap with `lifecycle=unsubscribed`).
- Reworking meal-stop / kitchen demand eligibility rules.

## Decisions

### 1. Shared service module location

**Decision:** Put canonical rules in `orders/services/customer_lifecycle.py` (subscriptions + deliveries are orders-domain), with thin wrappers in `user_management` for list/dashboard views.

**Alternatives:** New `churn` Django app (heavier for two models); all logic in `user_management` (wrong ownership of subscription cancel).

### 2. Lifecycle precedence (mutually exclusive)

**Decision:** Evaluate in order: `never_subscribed` → `unsubscribed` → `at_risk` → `won_back` → `active`.

**Won_back:** has active sub, not at_risk, and ∃ cancelled sub with churn_date < active.`started_on`.

### 3. At-risk low-balance days without history table (v1)

**Decision (v1):** Count blocked service days as: if currently `meal_service_blocked_low_balance`, number of Asia/Dhaka service days from `meal_service_blocked_at.date()` through today inclusive, capped to the last 7 service days; treat as blocked on those days. Additionally count distinct service dates in the last 7 where deliveries were system-skipped with a documented low-balance/cutoff-after-block note when present.

**Meal-offs:** distinct `service_date` in last 7 with skip_source in `{customer, admin}`.

**Wallet:** spendable balance < one-day cost from active subscription published/slot pricing helper already used for meal charges (document exact helper in implementation).

**Alternative considered:** New `CustomerMealServiceBlockDay` fact table written on each debit/cron evaluation — better accuracy; defer to follow-up if product needs intermittent historical blocks.

### 4. SubscriptionCancellation vs existing cancel_source

**Decision:** New model for reason_code/text; map `cancelled_by` enum to existing `cancel_source` values (`customer|admin|system`). Keep `CustomerSubscription.cancelled_by` user FK for actor identity. One reason row per cancel event (unique on subscription for first cancel; re-subscribe creates new subscription rows).

**reason_code `unknown`:** migration-only; serializer rejects from clients.

### 5. Cancel API contract

**Decision:** Require body field `reason_code`; optional `reason_text`. Inside `cancel_subscription` (or immediately after in the same transaction), create `SubscriptionCancellation`. Keep slot skip / wallet behavior owned by existing cancel service.

### 6. API surface

| Path | Role |
|------|------|
| `GET /api/v1/web/customers/` | Extend filters + enrichment |
| `GET /api/v1/web/churn/customers/` | Unsubscribed-focused list + `?format=csv` |
| `GET /api/v1/web/churn/analytics/` | Period analytics |
| `/api/v1/web/churn/follow-ups/` | CRUD |
| `GET /api/v1/web/dashboard/summary/` | Additive KPIs |

Mount under existing web URLConf next to admin customers/dashboard (prefer `user_management` views calling shared lifecycle services; models may live in `orders`).

### 7. Revenue lost

**Decision:** Sum monthly plan price snapshot for each churned subscription in period (meal package price at cancel, preferring subscription/meal price helpers already used for admin displays). Document currency BDT decimal string.

### 8. Performance

- Indexes: `(status, cancel_effective_on)`, `(status, cancelled_at)`, SubscriptionCancellation `(reason_code, created_at)`, ChurnFollowUp `(customer, status)`.
- List endpoints: annotate Exists for active sub / ever sub / at_risk predicates; `select_related` wallet/user; prefetch latest cancellation.
- Analytics: aggregate queries per breakdown; avoid loading all deliveries into Python.

## Risks / Trade-offs

- [At-risk low-balance history incomplete] → Document v1 approximation; optional later block-day fact table.
- [BREAKING cancel clients] → Coordinate frontend cancel modal + any mobile clients; return clear 422 field errors.
- [Analytics cost on large history] → Bound date ranges (max 366 days); paginate lists; index cancel dates.
- [Overlap with `inactive_subscription`] → Keep both; lifecycle is the preferred filter for new UI.
- [Double counting won_back vs dashboard] → Use same shared helpers for month KPIs.

## Migration Plan

1. Add models + indexes.
2. Data migration: for each cancelled subscription without a reason row, insert `reason_code=unknown`, `cancelled_by` from `cancel_source` or `unknown`→`system`/`customer` best-effort.
3. Deploy backend before frontend reason UI; old clients break on cancel until updated — ship frontend cancel reason in same release window.
4. Rollback: reverse migration removes new tables/fields; cancel reverts to optional reason (code rollback required for required validation).

## Open Questions

- Exact one-day meal cost helper name (reuse meal payment pricing vs package monthly/30) — resolve during apply by inspecting `orders/services` pricing helpers; prefer same source kitchen/wallet uses for a single day.
- Whether churn rate denominator is **customers** with active sub at period start or **subscription rows** — default **unique customers** with ≥1 active sub at period start.
