## Context

Meal packages are modeled as `MealCategory` with an integer AutoField primary key. Public list/detail live on `MealCategoryViewSet` under `/meals/` (`AllowAny` for GET). Responses currently include sequential `id`, and detail URLs are `/meals/<pk>/`.

Customer order create (`OrderCreateSerializer`) accepts `meal_id` as an integer PK. Public cycle offering (`build_public_cycle_offering`) also returns internal `plan_id` plus costing snapshots (`product_cost`, `profit`, `other_cost`).

Stakeholders: storefront/mobile customers (opaque IDs), admin/managers (keep integer FKs for cycle tooling), ops (safe migration of existing meals).

## Goals / Non-Goals

**Goals:**

- Keep integer PK for DB relations and Django admin internals.
- Expose opaque UUID `public_id` on public meal APIs and use it as the detail lookup key.
- Backfill existing rows safely; new rows get UUIDs automatically.
- Align customer order create with meal `public_id`.
- Tighten public offering payloads: no internal plan PK, no product/profit cost bands.
- Preserve listing, pricing, cycle offering (customer-safe), soft-delete, and admin meal CRUD behavior.
- Ship frontend-facing docs so clients know exactly what to change.

**Non-Goals:**

- Replacing integer PKs on `MealCycle`, `MealCyclePlan`, `Order`, or `Ingredient` in this change (except meal identity on customer surfaces).
- Dual-routing (accept both int and UUID) — integer public meal detail paths are intentionally retired.
- Changing cycle planning / costing calculation logic.
- Frontend application code outside this backend repo (docs only).

## Decisions

### 1. `public_id` on `MealCategory` only (meal package identity)

**Choice:** Add `UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)` to `MealCategory`.

**Rationale:** Public enumeration risk is highest on meal catalog URLs. Orders and plans remain internal FKs by integer PK.

**Alternatives considered:**

- UUID as primary key — rejected (breaks all FKs, larger migration surface).
- Hashids / opaque tokens — rejected (UUID is standard, unique, and well-supported by DRF/`uuid` path converters).

### 2. Lookup configuration

**Choice:** On `MealCategoryViewSet` set `lookup_field = "public_id"` and `lookup_url_kwarg = "public_id"`. DRF `DefaultRouter` will generate `/meals/<public_id>/`. Prefer explicit UUID path converter via custom router or `get_extra_actions` only if needed; otherwise rely on UUIDField validation (invalid UUID → 404).

**Rationale:** Matches requirement `/meals/<uuid:public_id>/` and removes sequential ID guessing.

### 3. Public vs admin serializers

**Choice:**

- Public list/detail (`MealListSerializer` / `MealDetailSerializer`): replace `id` with read-only `public_id`; keep pricing, thumbnail, description, `current_cycle_offering`.
- Create/update write serializer unchanged for writable fields; create/update responses use detail serializer with `public_id`.
- Admin/cycle brief serializers (`MealCategoryBriefSerializer` and admin cycle surfaces): may keep integer `id` for manager tooling **or** expose both `id` and `public_id` for admin convenience. Public/customer paths never return integer meal `id`.

**Rationale:** User asked for separate public vs admin exposure; managers still need stable internal references in cycle UIs.

### 4. Public offering scrub

**Choice:** Update `build_public_cycle_offering` to omit `plan_id`, `product_cost`, `profit` (and keep customer-useful fields: year/month, cycle_days, total_meals, package totals, per-meal rate, finalized_at, menu_items). Also omit `other_cost` for consistency with “no internal business costing”.

**Rationale:** User explicitly forbids product_cost, profit, and internal plan_id on public responses. Prior offering spec allowed cost bands; this change supersedes that for public clients.

**Alternatives considered:** Leave cost bands — rejected (contradicts current product requirement).

### 5. Order create meal reference

**Choice:** Change customer `OrderCreateSerializer` from `meal_id: IntegerField` to `meal_id: UUIDField` resolved via `MealCategory.objects.get(public_id=value)` (field name can stay `meal_id` for minimal client rename friction **or** rename to `meal_public_id`). Prefer renaming request field to `meal_public_id` for clarity and document the break; response order payloads that currently expose integer `meal` FK should expose `meal_public_id` (and optionally nested meal brief with `public_id`) on customer serializers.

**Rationale:** After browsing `/meals/<uuid>/`, clients must create orders with the same identifier. Keeping the name `meal_id` while accepting UUIDs is confusing.

**Decision locked:** Request field `meal_public_id` (UUID). Deprecate integer `meal_id` on customer create (remove in this change — single breaking cut).

### 6. Related nested IDs scope

| Surface | Decision |
|---------|----------|
| Public meal list/detail | `public_id` only |
| Customer today-menu package identity | Prefer `meal_public_id` / `public_id` instead of integer `meal_category_id` when exposed to customers |
| Admin menu-schedule / cycle-plan APIs | Keep integer `plan_id` / `meal_category_id` (admin-only) |
| Order / delivery admin web APIs | Keep integer order IDs for now (out of scope) |
| `MealCyclePlan.public_id` | Out of scope |

### 7. Migration strategy

**Choice:** Two-step or single migration with:

1. Add nullable `public_id` (or add with default and unique=False first if needed).
2. RunPython backfill `uuid.uuid4()` per existing row.
3. Alter field to `null=False`, `unique=True`.

Prefer Django-friendly pattern: add field with `default=uuid.uuid4` + unique; for existing DBs use a data migration that fills nulls if the generated migration leaves gaps. Never delete/recreate `MealCategory` rows.

### 8. Documentation deliverable

**Choice:** After implementation (apply phase), write:

- `meals/docs/frontend/meal-public-uuid.md` — client migration guide (list/detail URL, response fields, order create, removed fields).
- `meals/docs/backend/meal-public-uuid.md` — model/migration/API notes for backend maintainers.

## Risks / Trade-offs

- [Breaking URL + payload] → Document clearly; no dual support to avoid lingering sequential ID exposure.
- [Order create field rename] → Update order tests and frontend doc in same change.
- [Existing clients hard-coding meal PK] → 404 on old paths; migration checklist in frontend doc.
- [UUID in URLs longer / less memorable] → Acceptable for security/privacy.
- [Admin filters still use integer meal_category] → Intentional; do not change admin filter query params unless a public filter needs UUID.

## Migration Plan

1. Deploy migration (add + backfill `public_id`).
2. Deploy API code that switches lookup and serializers.
3. Clients switch to `public_id` / `meal_public_id` before or at the same release (coordinated break).
4. Rollback: revert API deploy first (URLs/serializers); DB column can remain (non-destructive). Do not drop `public_id` casually after clients adopt it.

## Open Questions

- None blocking — today-menu customer field rename is included as in-scope when that response exposes meal category identity to customers; if implementation finds the field only used internally, skip response change and note in tasks.
