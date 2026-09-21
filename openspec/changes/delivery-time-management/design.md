## Context

BeFood already has **operational** lunch/dinner concepts deeply wired into orders, kitchen, meal-off cutoffs (`MealOffSettings`), menu reveal (`MenuRevealSettings`), and delivery boards. Those are fixed `TextChoices` (`lunch` / `dinner`) and must stay stable.

Separately, product needs an **informational catalog** of delivery time windows (“Lunch 12:00–14:30”, “Dinner 19:00–21:30”, future “Breakfast”, “Sehri”, etc.) that admins can CRUD without code changes, and that customer UIs can display dynamically.

Closest existing patterns:

- **Backend catalog CRUD:** `faqs` (`FaqType` — `PublicIdMixin`, `name`, `sort_order`, `is_active`, hard delete, `IsVerifiedAdmin`, public list via `AllowAny`).
- **Time-of-day storage:** `models.TimeField` + `Asia/Dhaka` for meal-off and menu reveal (not absolute UTC datetimes).
- **Admin frontend CRUD:** FAQ types / Service Areas — modal + `react-hook-form` + zod + TanStack Query + `sonner` + `type="time"` inputs on Settings.
- **User marketing surface:** package detail already hardcodes delivery windows in `befood-frontend/src/features/monthly-package/data/detailStaticContent.ts` (`detailPolicies`: Lunch/Dinner Bangla times); homepage TrustStrip/ServiceHub mention lunch+dinner without clock times.

## Goals / Non-Goals

**Goals:**

- Dynamic `DeliverySchedule` records (name + daily start/end local times + active + sort order).
- Admin CRUD API + public active list API following project conventions (`public_id`, snake_case JSON, drf-spectacular).
- Admin UI “Delivery Times” and customer package-detail (then homepage) display fed only by API.
- Clear documentation that this catalog is display-oriented and independent of operational `meal_period`.

**Non-Goals:**

- Replacing or extending `MealCategory.MealPeriod` / `OrderDelivery.MealPeriod` with arbitrary types.
- Driving kitchen boards, meal-off eligibility, menu reveal, pricing, or order slot generation from this catalog (v1).
- Overnight windows (`end_time <= start_time`) in v1.
- Soft delete / slug fields (unless a later need appears).
- Mobile app UI (API may be reused later; v1 targets web admin + customer site).

## Decisions

### 1. New Django app `delivery_schedules` (not extend `orders` / `meals`)

- **Choice:** Dedicated app mirroring `faqs` / `announcements`.
- **Why:** Keeps informational catalog out of operational order/meal models; avoids implying that new types affect kitchen/order pipelines.
- **Alternatives:** Put model on `orders` next to `MealOffSettings` (rejected — conflates ops cutoffs with marketing windows); put in `app_config` (rejected — app_config is singleton-ish site config, not a multi-row catalog).

### 2. Model shape

```text
DeliverySchedule(PublicIdMixin)
  name          CharField(max_length=100, unique=True)
  start_time    TimeField
  end_time      TimeField
  is_active     BooleanField(default=True, db_index=True)
  sort_order    IntegerField(default=0)
  created_at    DateTimeField(auto_now_add=True)
  updated_at    DateTimeField(auto_now=True)
```

- **Field name `sort_order`** (not `displayOrder`) — matches `faqs`, operational costs.
- **No `slug`** — FAQ types do not use slug; names are human labels; `public_id` is the API identity.
- **`TimeField`** for start/end — same as meal-off/reveal; values are **Asia/Dhaka wall-clock** times for a typical service day. API serializes as `HH:MM:SS` (DRF default) or document `HH:MM` if serializers normalize — prefer consistent `HH:MM:SS` like reveal settings tests, with frontend formatting for display.
- **Unique `name`** (case-sensitive uniqueness at DB; validate strip + reject blank; recommend case-insensitive uniqueness check in `clean`/serializer to avoid `Lunch` vs `lunch`).

### 3. Validation (v1)

- `name` required after strip; unique.
- `start_time` / `end_time` required.
- **Require `start_time < end_time`** (same-day window only).
- Reject equal start/end.
- Overnight windows explicitly **out of scope**; document as future enhancement (would need `allows_overnight` or end-next-day semantics).

### 4. Delete semantics

- **Hard delete** (like FAQ types), not soft delete.
- No FK dependents in v1 → destroy always allowed (204).
- Deactivate via `is_active=false` when admin wants to hide without deleting.

### 5. API routing

Mirror FAQs mount style (top-level include in `core/urls.py`):

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/delivery-schedules/public/` | AllowAny | Active only, ordered by `sort_order`, `name`, `id` |
| GET/POST | `/delivery-schedules/` | IsVerifiedAdmin | Admin list/create |
| GET/PATCH/DELETE | `/delivery-schedules/{public_id}/` | IsVerifiedAdmin | Admin detail/update/delete |

- Use `DefaultRouter`; register `public` before the main list basename so `public` is not parsed as `public_id`.
- Pagination: admin list paginated (FAQ-like defaults); public list **unpaginated** small catalog (or soft max ~100) — same spirit as public FAQ catalog.
- Lookup: `public_id` (UUID).

### 6. Layering

- Thin ViewSets; serializers for shape; `services/` for create/update/delete helpers and public queryset if non-trivial.
- Model `clean()` for cross-field time rules; serializers call `full_clean` or duplicate validation for API errors.

### 7. Seed data

- Data migration seeds **Lunch** `12:30–14:30` and **Dinner** `19:00–21:00` if empty (idempotent), matching current package-detail static copy in `detailStaticContent.ts` so public UI stays continuous before first admin edit.
- Seeds are editable/deletable like any other row — not code constants.

### 8. Admin frontend

- Clone **Ingredients** or **FAQ type** modal CRUD (both RHF+zod+AdminModal); Ingredients is the simplest same-shape list.
- Files under `befood-frontend/src/features/admin/` + route in `config/routes.ts`, sidebar **System** (or Operations near Delivery) as “Delivery Times”.
- Forms: `react-hook-form` + zod; time via native `<Input type="time" />` (Settings `toInputTime`/`toApiTime` helpers if needed).
- API client uses existing `adminApi` axios instance; snake_case fields.
- Soft-delete elsewhere often means `is_active=False`; this catalog uses **hard delete** when admin deletes (no FKs), plus deactivate via `is_active` — same as FAQ types.

### 9. User frontend integration point

- **Primary:** Replace hardcoded Lunch/Dinner windows in `monthly-package/data/detailStaticContent.ts` (`detailPolicies`) and the package detail UI that renders them (`DetailHero` / related detail sections) with public API data — this is the existing user-facing delivery-window copy.
- **Secondary:** Homepage — optional `DeliveryTimesSection`, and/or make `TrustStrip` / `ServiceHub` dynamic from the same public list (today they say “২টি উইন্ডো · লাঞ্চ + ডিনার” statically).
- Fetch via `createPublicApiClient()` + TanStack Query; format times for `bn` display; do not hardcode schedule names or windows; empty → keep non-window policy rows or hide window rows only.

### 10. Docs & OpenAPI

- `extend_schema` / `extend_schema_view` on viewsets (drf-spectacular already wired at `/api/docs/`).
- Backend doc: `delivery_schedules/docs/backend/delivery-time-management.md`
- Frontend doc: `delivery_schedules/docs/frontend/delivery-time-management.md`

## Risks / Trade-offs

- **[Risk] Product confusion between delivery schedules and meal_period** → Mitigation: docs + admin UI copy stating “marketing/display windows only”; never wire into order generation in v1.
- **[Risk] Admin creates Breakfast but kitchen still only lunch/dinner** → Mitigation: expected; document; future phase may map schedules ↔ periods if product asks.
- **[Risk] Overnight windows needed later** → Mitigation: v1 validation documents limitation; additive `end_next_day` flag later without breaking same-day rows.
- **[Risk] Duplicate near-identical names** → Mitigation: unique constraint + strip; case-insensitive check in validation.
- **[Risk] Public endpoint caching** → Mitigation: small payload; optional short Cache-Control later; not required for v1.

## Migration Plan

1. Add app + model migration + optional seed data migration.
2. Ship APIs + tests.
3. Deploy backend; admin UI can follow immediately (same release preferred).
4. Ship package-detail dynamic windows (replace `detailStaticContent` hardcoding); optional homepage TrustStrip/section next.
5. Rollback: remove URL includes / disable UI; table can remain (harmless) or reverse migrations if unused.

## Open Questions

- Whether homepage TrustStrip should show dynamic count/names from API in the same phase as package detail (recommended if cheap).
- Whether admin Settings page should *link* to Delivery Times (avoid embedding duplicate Lunch/Dinner fields next to meal-off/reveal) — recommend sidebar entry only, keep Settings for operational cutoffs.
- Dedicated `delivery_schedules` app remains preferred over putting the catalog in `orders`/`meals`, to avoid implying operational `meal_period` replacement (full enum→FK migration is a separate future change).
