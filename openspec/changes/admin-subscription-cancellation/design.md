## Context

BeFood is **production-live**. Admin Customer 360 already surfaces active subscription and wallet (`AdminCustomerViewSet`, frontend `AdminCustomerDetailPage`), and customers can self-cancel via `CustomerSubscriptionViewSet.cancel_current` → `cancel_subscription()`. There is **no** admin cancel API/UI.

Verified production-relevant behavior (code, not assumptions):

| Area | Location | Behavior |
|------|----------|----------|
| Model | `orders/models.py` `CustomerSubscription` | `status` active\|cancelled; `cancelled_at`; `cancel_effective_on`; unique one active per customer; **no** `cancelled_by` |
| Active lookup | `orders/services/subscription_service.py` `get_active_subscription` | `status=active` |
| Cancel service | same file `cancel_subscription` | atomic + `select_for_update`; idempotent if already cancelled; sets `cancel_effective_on=business_today()`; bulk-skips only `SCHEDULED` with `service_date__gt` effective — **keeps all same-day slots** |
| Customer cancel API | `orders/api/subscription_views.py` `cancel_current` | `POST .../subscriptions/current/cancel/`, `IsVerifiedCustomer` |
| Admin subs API | `AdminSubscriptionViewSet` | list/retrieve + mark delivery only — **no cancel** |
| Admin 360 | `user_management/api/admin_customer_views.py` | `IsVerifiedAdmin`; active-subscription, wallet-overview, activity (`subscription_cancelled` already composed) |
| Cutoff | `orders/services/meal_off.py` `is_past_meal_cutoff` | `now_local > deadline` (exact cutoff still cancellable); TZ from `MealOffSettings` (default Asia/Dhaka) |
| Meal OFF | `orders/services/meal_off.py` `customer_meal_off` | soft `SKIPPED`/`customer`; no wallet move |
| Charge | `orders/services/meal_payment.py` `charge_delivered_meal` | on `delivered`; price from `MonthlyMenuSlot.final_meal_price_snapshot` via `slot_pricing.resolve_published_slot_for_delivery` |
| Withdrawable | `wallet/services/withdrawable.py` `compute_maximum_withdrawable` | always `max(0, recharge − meal_stop_threshold)`; not subscription-aware |
| Withdraw reserve | `wallet/services/funding.py` `request_withdraw` | immediate recharge debit + PENDING txn |
| Slot create cutoff | `ensure_subscription_deliveries` | uses `is_past_meal_cutoff` for **new** same-day rows only |

Frontend (`F:\befood\befood-frontend`): Active Subscription tab is display-only; customer cancel modal exists (`CancelSubscriptionModal` + `useCancelSubscription`); admin uses `AdminModal` + `sonner` + TanStack Query invalidation.

## Goals / Non-Goals

**Goals:**

- One canonical cancel path for admin + customer with per-slot lunch/dinner cutoff classification.
- Admin cancel (+ preview) from Customer 360 with verified-admin auth and actor audit.
- Post-cancel withdrawable: drop meal-stop floor; retain finalized-meal liability via published slot prices; same formula in GET wallet and `request_withdraw`.
- Soft-skip only; preserve history, delivered, charged, and already-skipped rows.
- Atomic cancel (subscription state + slot skips together); idempotent repeats.
- Frontend confirm UX; backend is source of truth for all financial/meal impact numbers.
- Production-safe tests + deploy/rollback plan.

**Non-Goals:**

- Refunding already-charged meals or reversing wallet PAYMENT rows.
- Hard-deleting `OrderDelivery` / ledger rows.
- Changing meal ON/OFF customer APIs, auto-delivery cron, or meal-stop **block** (auto-delivery pause) rules for active subscribers.
- New generic audit-log framework.
- Changing package pricing / menu publish.

---

## A. Current Backend Flow

1. **Subscribe:** `subscribe_customer` → `ensure_subscription_deliveries` creates horizon of `OrderDelivery` rows (order XOR subscription parent).
2. **Meal OFF/ON:** `customer_meal_off` / `customer_meal_on` — status toggles before deadline; charge only on deliver.
3. **Cancel (customer today):** `cancel_subscription` — status cancelled; future dates skipped; **today untouched**.
4. **Deliver + charge:** `mark_delivery` → `charge_delivered_meal` → `debit_wallet` with idempotency `meal-delivery:{public_id}`.
5. **Withdraw:** `request_withdraw` caps at `Wallet.withdrawable_balance` (threshold-based); reserves via immediate debit.
6. **Admin 360 read:** nested resources under `/api/v1/web/customers/{public_id}/`.

## B. Current Frontend Flow

- Page: `src/features/admin/pages/AdminCustomerDetailPage.tsx` — tab `active-subscription` → inline `ActiveSubscription()`.
- APIs: `src/features/admin/api/adminCustomerApi.ts` + hooks `useAdminCustomers.ts`.
- No admin cancel mutation. Customer cancel: `subscriptionsApi.cancelCurrentSubscription` → `POST /api/v1/subscriptions/current/cancel/`.

## C. Existing Logic We Can Reuse

- `cancel_subscription` skeleton (lock, status, bulk skip, idempotency).
- `is_past_meal_cutoff` / `meal_off_business_now` / `business_today` / `get_meal_off_settings`.
- Soft-skip pattern (`SKIPPED` + `SkipSource.SYSTEM` + note) — same as cancel today and cutoff create.
- `resolve_published_slot_for_delivery` / `_resolve_charge_amount` for liability estimates (read-only).
- `compute_maximum_withdrawable` (extend signature; keep active path).
- `IsVerifiedAdmin` + admin customer nested action pattern (e.g. delivery-fee POST).
- Activity feed already emits `subscription_cancelled` from `cancelled_at`.
- Frontend: `AdminModal`, `CancelSubscriptionModal` UX, `invalidateCustomerCaches` / `invalidateSubscriptionCaches`, `getApiErrorMessage` + `toast`.

## D. Gaps

1. No admin cancel/preview endpoint.
2. Cancel ignores same-day peri-cutoff lunch vs dinner.
3. Withdrawable ignores subscription status and finalized meal liability.
4. No `cancelled_by` / `cancel_source` on subscription.
5. No admin cancel UI.
6. Customer cancel tests assert “today stays scheduled” — must update when shared semantics change.

## E. Proposed Backend Changes (file-by-file)

| File | Change | Why |
|------|--------|-----|
| `orders/services/subscription_service.py` | Rewrite skip selection in `cancel_subscription`: classify each `SCHEDULED` delivery with `is_past_meal_cutoff`; skip if not past; preserve if past or non-scheduled; accept optional `cancelled_by`, `cancel_source`, `reason`; keep atomic + idempotent | Canonical shared rules |
| `orders/models.py` + migration | Additive nullable `cancelled_by` (FK User), `cancel_source` (customer\|admin\|system) | Admin audit without new table |
| `orders/api/subscription_views.py` | Pass `cancel_source=customer` into service from `cancel_current` | Shared service metadata |
| `user_management/api/admin_customer_views.py` | `POST .../cancel-subscription/` (+ `GET .../cancel-subscription-preview/`) `IsVerifiedAdmin` | Admin surface on 360 |
| Serializers / OpenAPI next to admin customer + subscription | Preview + cancel response DTOs | Contract |
| `wallet/services/withdrawable.py` (+ callers: `Wallet.withdrawable_balance`, `funding.request_withdraw`, serializers) | Branch: active → threshold; else → liability of past-cutoff `SCHEDULED` slots | Post-cancel withdraw rules |
| `orders/services/meal_payment.py` or small helper | Read-only `estimate_delivery_charge(delivery)` shared with withdrawable | Single pricing source |
| `user_management/services/admin_customer.py` | Enrich activity refs with `cancel_source` / actor when present | Audit visibility |
| Tests | See §L | Production safety |
| Docs | `orders/docs/backend/...`, wallet docs update withdrawable | Guideline |

## F. Proposed Frontend Changes (`befood-frontend`)

| File | Change |
|------|--------|
| `adminCustomerApi.ts` | `getAdminCancelSubscriptionPreview`, `postAdminCancelSubscription` |
| `useAdminCustomers.ts` | mutation + invalidate activeSubscription, subscriptions, detail, walletOverview, meals, activity, subscription list/detail |
| `AdminCancelSubscriptionModal.tsx` (new) | `AdminModal`; load preview; confirm; Bangla/English copy per product |
| `AdminCustomerDetailPage.tsx` `ActiveSubscription` | Button when `status==='active'` && verified admin |
| Types in `customerManagementTypes.ts` | Preview/cancel response types |

## G. Exact Cancellation Algorithm

```text
request (admin or customer)
→ permission check (IsVerifiedAdmin | IsVerifiedCustomer)
→ resolve customer + active subscription (404 if none for actor rules)
→ BEGIN atomic
→ select_for_update(subscription)
→ if already CANCELLED: return idempotent success (no re-skip side effects beyond no-op filter)
→ now = meal_off_business_now(); today = business_today()
→ settings = get_meal_off_settings()
→ load SCHEDULED deliveries for subscription (select_for_update of self if updating per-row; or classify then bulk update by id list)
→ for each SCHEDULED row:
     if is_past_meal_cutoff(service_date, meal_period, now=now): PRESERVE (finalized)
     else: mark SKIPPED / SYSTEM / note e.g. 'Skipped after subscription cancel.'
→ never touch delivered | skipped | missed
→ set status=CANCELLED, cancelled_at=now_utc, cancel_effective_on=today
   (or last preserved service_date if product prefers; default today matches live_delivery_q for preserved same-day)
→ set cancelled_by / cancel_source when provided
→ COMMIT
→ build response: cancelled/preserved meal summaries + wallet snapshot (withdrawable after new formula)
```

**Boundary:** Exact cutoff instant → `is_past_meal_cutoff` is False → slot **is cancellable** (matches meal-off).

**Preview:** Same classification + liability math in a read-only transaction (no writes); recommended for admin confirm modal.

## H. Wallet / Withdrawal Formula

Let `R` = `wallet.recharge_balance` (pending withdraw already reduced `R`).  
Let `T` = `OrderWalletSettings.meal_stop_threshold`.  
Let `L` = sum of published `final_meal_price_snapshot` for customer’s `SCHEDULED` deliveries where `is_past_meal_cutoff` is True (typically preserved post-cancel slots). Missing slot price → treat conservatively (fail preview/cancel validation or use 0 with logged error — prefer fail-closed on admin preview; withdraw path: if price missing, include no under-reserve — **decision: fail-closed exclude withdraw above R−known L and surface warning in preview**).

**Active subscription** (`get_active_subscription` not None):

```text
withdrawable = max(0, R − T)
```

**No active subscription:**

```text
withdrawable = max(0, R − L)
```

(`L = 0` ⇒ full recharge withdrawable; meal-stop threshold does not apply.)

Commission never withdrawable (unchanged).  
`request_withdraw` MUST use the same helper as `Wallet.withdrawable_balance` / serializer.

## I. API Contract

**Admin preview (recommended):**

```http
GET /api/v1/web/customers/{public_id}/cancel-subscription-preview/
Authorization: Token … (verified admin)
```

**Admin cancel:**

```http
POST /api/v1/web/customers/{public_id}/cancel-subscription/
Idempotency-Key: optional
Content-Type: application/json

{ "reason": "optional string" }
```

**Response (200) shape (snake_case; illustrative):**

```json
{
  "subscription": {
    "public_id": "...",
    "status": "cancelled",
    "cancelled_at": "2026-09-28T11:00:00+06:00",
    "cancel_effective_on": "2026-09-28",
    "cancel_source": "admin",
    "cancelled_by": { "id": 1, "email": "admin@..." }
  },
  "cancelled_meals": [
    { "public_id": "...", "service_date": "2026-09-28", "meal_period": "dinner", "estimated_charge": "80.00" }
  ],
  "preserved_finalized_meals": [
    { "public_id": "...", "service_date": "2026-09-28", "meal_period": "lunch", "estimated_charge": "80.00" }
  ],
  "wallet": {
    "balance": "300.00",
    "recharge_balance": "300.00",
    "meal_stop_threshold": "100.00",
    "finalized_meal_liability": "80.00",
    "withdrawable_balance": "220.00"
  }
}
```

Customer path remains `POST /api/v1/subscriptions/current/cancel/` but gains shared skip semantics; response may stay existing serializer (additive fields OK).

Errors: 401/403; 404 no active sub (admin: no active for that customer); 409 conflict on concurrent cancel races if needed; 422 validation.

## J. Database / Migration Impact

- Prefer **additive** nullable columns on `CustomerSubscription`: `cancelled_by_id`, `cancel_source`.
- No change required to `OrderDelivery` schema (reuse status/skip_source/note).
- No hard-delete migrations.
- Deploy: migrate before/with backend that writes new fields; old rows null = historical customer cancels.

## K. Risk Analysis

| Risk | Mitigation |
|------|------------|
| Same-day dinner cancelled unexpectedly for self-cancel users | Release note; semantics match meal-off; exact cutoff still allowed |
| Under-reserved withdraw if slot price missing | Preview fail-closed; withdraw uses known L; monitor `MEAL_SLOT_PRICE_MISSING` |
| Partial cancel | Single `transaction.atomic` + subscription row lock |
| Double cancel / double-click | Idempotent service; optional Idempotency-Key |
| Cancel vs charge race | Deliver path locks delivery; skipped rows not auto-delivered; charged stays charged |
| Cancel vs withdraw race | Withdraw locks wallet + immediate reserve; withdrawable recomputed under lock |
| Kitchen/rider board | Soft-skip removes from cooking counts; preserved finalized stay scheduled |
| Frontend openspec root is backend-only | Implement frontend in sibling repo; contract documented here |

## L. Test Plan

**Cutoff / cancel:** before/after lunch; before/after dinner; exact boundary (`==` deadline → cancel); lunch passed dinner not; both passed; future days skipped; delivered untouched; already customer meal-off untouched; missing OrderDelivery; duplicate cancel idempotent.

**Wallet:** active threshold unchanged; after cancel threshold off; liability retains; withdraw above withdrawable rejected; after charge clears liability full remainder withdrawable; pending withdraw + cancel.

**Auth:** customer token denied on admin endpoint; unverified admin 403; verified admin 200.

**Concurrency:** two admins cancel; customer+admin cancel; cancel during mark-delivered where feasible.

**Frontend:** modal confirm; preview render; mutation invalidation; button hidden when no active sub / unverified.

## M. Deployment Plan

1. Ship backend + migration (cancel semantics + withdrawable + admin APIs).
2. Smoke: customer cancel, admin preview/cancel staging, withdraw after cancel with/without finalized dinner.
3. Ship frontend cancel button (old UI without button remains compatible with new backend).
4. Announce customer self-cancel same-day behavior change.

## N. Rollback Plan

- Feature-flag optional: if needed, gate new skip loop behind setting (default on after bake); else revert deploy.
- Migration rollback: drop nullable columns only if unused; safe to leave columns.
- Frontend: hide/remove button — admin API unused.
- Do **not** un-skip deliveries automatically on rollback (would re-open cancelled futures); manual support if required.

## Decisions

1. **Shared service enhancement over admin-only fork** — Prevents rule drift (proposal §13). Alternative: admin-only cutoff logic → rejected.
2. **Soft-skip not hard-delete** — Matches meal-off / current cancel; preserves kitchen/history. Alternative: delete rows → rejected for production.
3. **Cutoff comparison = existing `is_past_meal_cutoff` (`>`)** — At exact `16:00:00` slot still cancellable. Alternative: `>=` → inconsistent with meal-off.
4. **Admin endpoints on customer 360** `.../cancel-subscription[-preview]/` — Matches where UI lives; reuses `IsVerifiedAdmin` + public_id. Alternative: only on `AdminSubscriptionViewSet` → less discoverable from 360 (optional second alias later).
5. **Preview GET recommended** — Destructive + financial; avoids frontend calculating liability. Alternative: cancel-only → poorer UX.
6. **Additive `cancelled_by` / `cancel_source`** — Minimal migration; no new audit table. Alternative: note-only → weaker admin attribution.
7. **Withdrawable branch by active subscription presence** — Active keeps threshold; cancelled uses `L`. Alternative: always `max(T, L)` → would keep threshold after cancel (violates product).
8. **Liability pricing = published slot snapshot** — Same as charge path; not package list price. Quantity = one charge per delivery row.

## Risks / Trade-offs

- [Customer same-day surprise] → Document + align with meal-off mental model; QA matrix before prod.
- [Liability estimate ≠ final charge if menu republished] → Accept same risk as charge path; charge still uses live published slot at deliver time; prefer locking liability to snapshot at cancel time in metadata for support (optional enhancement).
- [OpenSpec repo is backend] → Frontend tasks executed in `befood-frontend` with contract from this design.

## Migration Plan

See §J, §M, §N.

## Open Questions

1. Should `cancel_effective_on` become “last preserved service date” when all same-day slots are skipped (vs always `business_today()`)? **Recommendation:** keep `business_today()` unless product wants overview “expires” to show yesterday when nothing preserved.
2. Bangla vs English admin modal copy — product polish after functional UI.
3. Optional feature flag for cutoff-aware skip during first production week — recommend only if release risk is high.
