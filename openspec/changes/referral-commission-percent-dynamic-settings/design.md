## Context

Referral accrual already runs on meal delivery complete via `credit_referral_commission_for_delivery` in `referrals/services/commission.py`. The rate comes from:

```python
def commission_percent() -> Decimal:
    raw = getattr(settings, 'REFERRAL_COMMISSION_PERCENT', '5')
    return Decimal(str(raw)).quantize(Decimal('0.01'))
```

`REFERRAL_COMMISSION_PERCENT` is env-backed in `core/settings/base.py` (default `'5'`). Each `ReferralCommission` row already stores `commission_percent` and `commission_amount` at write time.

Admin-editable business settings elsewhere use **singleton DB models** + `IsVerifiedAdmin` GET/PATCH under `/api/v1/web/...`, e.g.:

| Setting | Model | API |
|---------|-------|-----|
| Wallet thresholds | `OrderWalletSettings` | `GET/PATCH /api/v1/web/orders/order-wallet-settings/` |
| Meal-off cutoffs | `MealOffSettings` | `GET/PATCH /api/v1/web/orders/meal-off-settings/` |
| Onahar | Onahar settings | `GET/PATCH /api/v1/web/onahar/settings/` |

There is **no** generic key-value `SystemSetting` table. Admin Frontend Settings (`http://localhost:5173/admin/settings`) already consumes these per-domain settings endpoints.

Stakeholders: finance/ops (rate changes), verified admins (UI), engineering (safe live deploy).

## Goals / Non-Goals

**Goals:**

- Make referral commission % editable by verified admins without code/deploy.
- Apply the live rate only when **creating / upgrading accrual** for future (and pending-upgrade) calculations; leave historical rows immutable.
- Follow existing singleton-settings + web admin API patterns.
- Ship backend + Admin Frontend plan together; document contracts for the settings page.
- Keep accrual + wallet debit/credit atomic; read percent inside the same transactional accrual path.

**Non-Goals:**

- Recalculating or rewriting past `ReferralCommission` rows, wallet balances, or Admin Wallet history.
- Generic multi-key configuration platform / arbitrary settings registry.
- Customer-facing rate editor.
- Changing eligibility rules, reverse/manual adjust semantics, or reconcile write behavior beyond percent source.
- Making env the sole source of truth after DB seed (env remains seed/fallback only).

## Decisions

### D1 — Singleton `ReferralProgramSettings` in `referrals` (not env-only, not generic KV)

**Choice:** Add `ReferralProgramSettings` singleton (`pk=1`) with `commission_percent` DecimalField (0–100, 2 dp), `updated_at`, `.load()` / forced `pk=1` save, same as `OrderWalletSettings`.

**Why:** Matches proven BeFood admin-settings pattern; no new cross-app dependency; clear ownership inside `referrals`.

**Alternatives:**

| Option | Rejected because |
|--------|------------------|
| Env / Django settings only | Cannot edit from admin UI without redeploy |
| Generic `SystemSetting` key-value | No existing table; overkill for one field; weaker typing/validation |
| Put field on `OrderWalletSettings` | Wrong domain; couples unrelated settings |

### D2 — Runtime read path

**Choice:** `commission_percent()` loads `ReferralProgramSettings.load().commission_percent`. Migration / first `load()` seeds from `settings.REFERRAL_COMMISSION_PERCENT` (default `5`) if creating the row.

**Why:** One function already centralizes the rate; callers (`credit_referral_commission_for_delivery`, skip markers, manual paths that need current default) stay unchanged.

**Cache:** Do **not** introduce long-lived process cache for the percent in v1. Singleton read is cheap; avoids stale multi-worker rates. If later cached, PATCH MUST invalidate (document as follow-up). No existing cache for this value today.

### D3 — API path and response shape

**Choice (project convention):**

```text
GET|PATCH /api/v1/web/referrals/settings/
```

Permission: `IsVerifiedAdmin`. Mount on `referrals/api/web_urls.py` (and shared alias if other referral web routes use both).

Response fields (snake_case, money/percent as decimal strings consistent with wallet settings):

```json
{
  "referral_commission_percent": "5.00",
  "updated_at": "2026-09-11T00:00:00Z"
}
```

PATCH body: `{ "referral_commission_percent": "10.00" }` (partial). Success returns the updated resource (same as OrderWalletSettings), not a free-form `message` wrapper — keep list/detail settings consistency. Frontend may show a toast from HTTP 200.

**User-suggested path** `/api/v1/admin/settings/referral/` is **not** used: BeFood admin panel APIs live under `/api/v1/web/...`. Document the chosen path clearly in frontend docs so the settings page wires correctly.

### D4 — Validation

- Inclusive range: `0 <= referral_commission_percent <= 100`
- At most 2 decimal places
- Reject negatives and values > 100 with field errors (400/serializer validation, matching project style)
- Allow `0` (pause commission payouts without disabling the whole referral program flag)

### D5 — Future-only financial rule

- Successful accruals already persist `commission_percent` on the row; that snapshot is authoritative for history/export/UI.
- Changing the setting MUST NOT trigger batch recalculation.
- When an existing `skipped` row is **upgraded in place** to `success`, use the **current** live percent at upgrade time (same as today’s env read at upgrade). Document this so finance knows mid-flight skips pick up the new rate when they become payable — still “future application,” not rewriting already-`success` amounts.
- Already-`success` / `reversed` / terminal `failed` rows: never overwrite percent/amount because of a settings PATCH.

### D6 — Admin Frontend (parallel plan)

Admin app (Vite, `/admin/settings`):

- Add **Referral Settings** section / `ReferralCommissionSetting` component beside existing settings cards (wallet thresholds, meal-off, etc.).
- On mount: `GET /api/v1/web/referrals/settings/` with admin JWT + `X-Client-Type: web`.
- Save: `PATCH` with validated `0–100` client-side; rely on backend for authoritative validation.
- Show current %, input, Save, success/error toasts; disable for non-verified admin (route already gated).

Backend repo delivers API + `referrals/docs/frontend/` contract; Admin Frontend repo implements the UI against that contract in the same delivery train.

### D7 — Files likely touched (backend)

| Area | Files |
|------|--------|
| Model + migration | `referrals/models.py`, `referrals/migrations/000x_...py` |
| Read/update service | `referrals/services/settings.py` (new), `commission.py` (`commission_percent`) |
| API | `referrals/api/serializers.py`, `views.py`, `web_urls.py`, `openapi.py` |
| Admin (optional Django admin) | `referrals/admin.py` |
| Config comment | `core/settings/base.py` (document seed/fallback) |
| Tests | `referrals/tests/test_referral_core.py`, `test_referral_api.py` |
| Docs | `referrals/docs/backend/...`, `referrals/docs/frontend/...` |

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Multi-worker stale rate if someone adds aggressive caching later | v1: no cache; document invalidation if cache added |
| Ops expects `/api/v1/admin/settings/referral/` | Docs + OpenAPI use `/api/v1/web/referrals/settings/`; frontend plan uses that |
| Accidental historical rewrite scripts | Spec + tasks forbid backfill of commission amounts; no migration updates existing commission rows |
| Race: PATCH during accrual | Accrual reads percent inside its DB transaction; acceptable slight cross-request race (same as any settings change mid-flight) |
| Seed differs from historical env on some environments | Migration default `5.00` + `load()` from current `settings.REFERRAL_COMMISSION_PERCENT` so deploy picks live env once |

## Migration Plan

1. Deploy migration creating `ReferralProgramSettings` with `commission_percent` default `5.00`; data migration or `load()` seeds from env if present.
2. Deploy code that reads DB via `commission_percent()`.
3. Deploy Admin Frontend settings UI calling the new endpoints.
4. Verify GET returns expected percent; PATCH to a test value in staging; complete one delivery and confirm new commission row uses new percent; prior SUCCESS rows unchanged.
5. Rollback: revert frontend section; revert backend to env-only read if needed; leave DB row in place (harmless). Do **not** reverse-migrate commission history.

## Open Questions

- None blocking: API path follows `/api/v1/web/...` convention (resolved vs user draft path).
- Optional later: audit log of who changed the percent (`updated_by`) — nice-to-have, not required for v1 (`updated_at` only).
