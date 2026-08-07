## Context

BeFood already tracks per-slot meal fulfillment via `OrderDelivery` (`scheduled` → `delivered` / `skipped` / `missed`) and charges wallets on successful delivery. There is no charity/contribution subsystem today. Product wants the “অনাহার” campaign: every N eligible delivered meals in a calendar month become 1 donated meal credit in a transparent public fund, with admin-managed distributions and privacy-aware leaderboards.

Stakeholders: public website visitors (no login), authenticated customers, verified admins, marketing (emotional messaging), and future frontend apps that must integrate from docs alone.

Constraints:
- Follow project patterns: new Django app, service layer, thin DRF views, `PublicIdMixin`, `IsVerifiedAdmin` for web admin, JWT/token auth for customers, problem-style / project error envelopes.
- Multi-client: lean public payloads; richer admin nesting OK under `/api/v1/web/...`.
- Money remains in `wallet`; Onahar unit is **meals**, never BDT.
- Statistics MUST derive from ledgers/aggregates—no hard-coded marketing numbers.

## Goals / Non-Goals

**Goals:**
- Correct, idempotent monthly contribution math with admin-configurable target and historical target snapshots.
- Append-only fund ledger; distribution publish debits fund; available balance enforced.
- Public transparency APIs (stats, leaderboard, ledger, distributions + media).
- Customer dashboard APIs (progress, history, privacy).
- Verified-admin APIs (target, distributions, audit visibility).
- Hooks from delivery success and refund/reversal into Onahar processing.
- Idempotent month-end job for expiry/finalization.
- Backend + frontend documentation.

**Non-Goals:**
- Accepting cash donations into Onahar Fund (meal credits only from eligible deliveries).
- Third-party NGO payment settlement or logistics dispatch.
- Push/SMS/email notification delivery infrastructure (may emit event payloads / document message copy; sending is optional/later).
- Contribution streaks, badges, or gamification beyond ranking (document as future).
- Admin override to distribute more meals than available fund (v1 rejects; override deferred).
- Changing wallet debit rules or order-delivery status machine itself beyond adding Onahar hooks.
- Mobile-only special routes (shared `/onahar/` + web admin mount is enough for v1).

## Decisions

### 1. New bounded context: `onahar` app
- **Choice:** Create `onahar/` as its own app (models, services, api, management commands, docs, tests). Mount public/customer routes at `onahar/` and admin at `api/v1/web/onahar/`.
- **Rationale:** Charity fund + transparency is a distinct domain from orders/wallet; keeps ledger and public APIs cohesive.
- **Alternatives considered:**
  - Fold into `orders/` — mixes fulfillment with marketing/charity; harder public surface.
  - Fold into `wallet/` — wrong unit (money vs meals).

### 2. Eligible unit = successfully `delivered` `OrderDelivery` slot
- **Choice:** Credit **1 Onahar Point** when an `OrderDelivery` becomes `delivered` for a registered customer. Skipped/missed/cancelled/refunded-as-undone slots do not credit. Package-level `Order` completion alone does not credit.
- **Rationale:** Matches “1 meal = 1 point” and existing delivery-centric ops; monthly packages create many slots, so counting package orders would under-count social impact.
- **Alternatives considered:**
  - Count package order create — wrong granularity vs marketing copy.
  - Count wallet debits — couples charity to payment success edge cases; delivery status is the operational truth.

### 3. Idempotent point events keyed by delivery
- **Choice:** Persist `OnaharPointEvent` with unique constraint on `order_delivery_id` (and direction/type), or unique `(delivery, event_type)` for credit vs reverse. Processing uses `transaction.atomic()` + existence check / unique violation handling. Never invent points without a delivery FK (except explicit admin adjustment rows if needed later—not in v1 customer path).
- **Rationale:** Mark-delivered retries already exist in orders; Onahar must mirror wallet’s “at most once per delivery” guarantee.
- **Alternatives considered:** Soft “processed” flag on `OrderDelivery` only — weaker audit; prefer explicit event table.

### 4. Monthly cycle math and target snapshot
- **Choice:**
  - Progress is keyed by `(customer, year_month)` where `year_month` is `YYYY-MM` in Asia/Dhaka (or project timezone).
  - On first activity in a month (or at month open), bind `target_snapshot` = current global `OnaharSettings.contribution_target` (default 50, min 1).
  - `contributions_earned = floor(net_eligible_points / target_snapshot)`; `remaining_points = net % target`.
  - When net points cross new multiples mid-month, create `OnaharContribution` rows immediately and credit fund ledger (+1 meal each).
  - Month-end job freezes the row: expires remaining points (history preserved), does not create further contributions from expired remainder, marks cycle `closed`. Job is idempotent via cycle status.
  - Changing global target mid-month updates **new** months / not-yet-snapshotted cycles; already-snapshotted open cycles keep their snapshot (document clearly). Optionally allow “apply to current open cycles” as an explicit admin flag—default **do not rewrite** open-cycle snapshots.
- **Rationale:** Product requires independent months and historical stability when target changes.
- **Alternatives considered:**
  - Recalculate entire history when target changes — breaks trust.
  - Only convert contributions at month end — delays emotional feedback; prefer immediate conversion when threshold crossed.

### 5. Refund / reversal adjustment
- **Choice:** If a previously credited delivery is reversed (refunded / undelivered after credit), write a reversing point event (−1) for that delivery (unique reverse event). Recompute month net points. If contributions already issued exceed `floor(new_net / target)`, create **adjustment** contribution/fund ledger entries (negative contribution or compensating debit) so totals stay honest, with audit log. Never silently delete historical contribution rows; use compensating records.
- **Rationale:** Public stats must remain explainable under audit.
- **Alternatives considered:** Block refunds after contribution — too rigid for ops; adjust instead.

### 6. Fund ledger as source of truth
- **Choice:** `OnaharFundLedgerEntry` append-only: `direction` credit|debit, positive `meals` integer, `entry_type` (`contribution` | `contribution_adjustment` | `distribution` | `distribution_restore`), FKs to contribution or distribution when applicable, `balance_after` cached optional. Available meals = sum(credits) − sum(debits). Do not rely solely on a mutable counter without ledger rows (may cache denormalized totals updated in same transaction).
- **Rationale:** Same professional pattern as wallet ledger; enables public transparency ledger.
- **Alternatives considered:** Single counter field — fails audit requirement §20.

### 7. Distribution lifecycle
- **Choice:** Distributions have statuses: `draft` → `published` → (`cancelled`). Only `published` debits fund. Publish is transactional: validate `meals_distributed <= available`, write ledger debit, set published metadata (`published_by`, `published_at`). Cancel published restores fund via compensating credit ledger entry and marks cancelled (images retained). Edits to meal count after publish require cancel+recreate or explicit adjustment path—v1: **meal count immutable after publish**; draft remains editable.
- **Rationale:** Prevents fund races and confusing partial edits.
- **Alternatives considered:** Live-edit published counts — error-prone for public pages.

### 8. Privacy display names
- **Choice:** `OnaharPrivacyPreference` per customer: `public` | `partial` | `anonymous` (default `partial` or `public`—prefer default **`partial`** for safety). Public APIs never expose email, phone, address, integer user id. Partial masks given/family name characters; anonymous shows a stable label like `Anonymous Contributor` (optionally with opaque public contributor token, not user id).
- **Rationale:** Product §8; default partial reduces accidental PII leak.
- **Alternatives considered:** Default public — stronger marketing, weaker privacy.

### 9. Hook integration point
- **Choice:** Call `onahar.services.credit_for_delivery(delivery)` from the same service path that successfully marks delivery `delivered` (and reverse from refund/undo paths). Prefer explicit service call over loose Django signals for testability; signals allowed as thin adapters if import cycles require it.
- **Rationale:** Keeps transaction boundaries clear with wallet debit.
- **Alternatives considered:** Nightly batch only — delays progress UX; use hooks + optional reconcile command.

### 10. API surface (v1)
- **Public (AllowAny):**
  - `GET /onahar/stats/`
  - `GET /onahar/leaderboard/`
  - `GET /onahar/ledger/` (paginated contribution + distribution sides or unified feed)
  - `GET /onahar/distributions/` + `GET /onahar/distributions/{public_id}/`
- **Customer (auth + customer profile):**
  - `GET /onahar/me/` (progress + lifetime + ranking)
  - `GET /onahar/me/history/`
  - `GET|PATCH /onahar/me/privacy/`
- **Admin (`IsVerifiedAdmin`):**
  - `GET|PATCH /api/v1/web/onahar/settings/` (target + history)
  - CRUD-ish distributions under `/api/v1/web/onahar/distributions/` including publish/cancel and media upload
  - `GET /api/v1/web/onahar/fund/` and audit list endpoints as needed
- **Rationale:** Matches multi-client routing; public stays cache-friendly and PII-safe.

### 11. Media storage
- **Choice:** `OnaharDistributionMedia` with ImageField (and optional external URL for video later). Serve via existing media URL pattern; validate type/size in serializers. Public detail returns absolute/media URLs.
- **Rationale:** Same as meal thumbnails / blog images.
- **Alternatives considered:** External CDN-only — unnecessary for v1.

### 12. Month-end automation
- **Choice:** Management command `close_onahar_month --month YYYY-MM` (default: previous calendar month). Scheduler (cron/CI) invokes after month boundary. Idempotent: skip already `closed` cycles; finalize contributions already created; expire remainders; write audit `month_closed`.
- **Rationale:** Explicit ops control + safe re-runs.
- **Alternatives considered:** Only lazy close on first next-month read — still implement command for deterministic reporting.

## Risks / Trade-offs

- **[Risk] Delivery hook missed on some code path** → Mitigation: reconciliation command that scans `delivered` without point events; admin alert via logs; tests cover primary mark-delivered path.
- **[Risk] Mid-month target change confusion** → Mitigation: snapshot per cycle; document that open cycles keep snapshot unless explicit apply flag (default off).
- **[Risk] Refund after contribution reduces fund below zero if already distributed** → Mitigation: allow negative *adjustments* on contribution side / track “outstanding adjustment”; still block new distributions when available ≤ 0; surface `adjustment_pending` in admin stats; never invent fake deliveries.
- **[Risk] Public leaderboard performance** → Mitigation: aggregate table or indexed contribution sums; paginate; cache stats endpoint briefly (e.g. 30–60s) with invalidation on contribution/distribution publish.
- **[Risk] Timezone boundary bugs** → Mitigation: single canonical timezone (project `TIME_ZONE`, expect Asia/Dhaka); store `year_month` string; tests around month edges.
- **[Trade-off] Immediate contribution vs month-end only** → Immediate conversion improves emotional UX; month-end still required for expiry of remainder.

## Migration Plan

1. Add `onahar` app + migrations; register in `INSTALLED_APPS`; seed default settings row (target=50).
2. Mount URLs; ship APIs behind feature completeness (no partial public numbers).
3. Deploy hook into delivery success / reverse paths in the same release as models.
4. Backfill: v1 **does not** auto-backfill historical deliveries unless product requests a one-off command (default: start counting from launch date; document launch cutoff).
5. Schedule `close_onahar_month` after go-live.
6. Rollback: disable hooks via settings flag `ONAHAR_ENABLED` if needed; keep tables; public endpoints can return empty/disabled message.

## Open Questions

- Exact default privacy mode (`partial` vs `public`) — design defaults to **`partial`**; product may override before apply.
- Whether lunch+dinner same day counts as 2 points — **yes** (each delivered slot); confirm with product if they intended “per calendar day” instead.
- Whether `missed` then later `delivered` is possible in orders — follow orders state machine; Onahar only credits on transition into `delivered`.
- Homepage teaser: same as `GET /onahar/stats/` or a reduced field set — prefer reuse of stats endpoint.
- Notification channel for contribution congratulations — document copy only in v1 unless an existing notification bus is trivial to call.
