## Context

BEFOOD currently tracks meal packages, ingredient *costing* catalogs, and orders. Durable kitchen/office equipment (refrigerators, burners, cookware, furniture, lights, computers, etc.) has no home in the data model. Frontend admin users (verified `ADMIN` / superuser via Token + `IsVerifiedAdmin`) need a management surface to register and maintain these items without conflating them with food inventory or meal cycles.

Existing patterns to mirror: `notices` / `Ingredient` admin CRUD (`PublicIdMixin`, `IsVerifiedAdmin`, `lookup_field='public_id'`, django-filter + pagination, services for domain rules, OpenAPI + docs). Runtime tenancy is `BusinessProfile` → `Outlet` (no company/branch entities yet).

## Goals / Non-Goals

**Goals:**

- Ship a dedicated `assets` Django app for permanent (non-consumable) asset tracking.
- Support categories and individual asset records suitable for kitchens and offices.
- Verified-admin REST API for frontend admin: full CRUD, filter/search/sort/paginate.
- Clear lifecycle statuses (in service, maintenance, retired, disposed) with soft retirement preferred over silent hard-delete of historical records.
- Optional location via `Outlet`; purchase/warranty metadata for ops visibility.
- Hard boundary from food/ingredient/order domains.

**Non-Goals:**

- Consumable stock, purchase orders, warehouse ledgers, or cooking quantity deduction.
- Depreciation accounting, GL integration, or tax amortization engines.
- Customer/public or rider/mobile APIs.
- QR scan workflows, maintenance work orders, or vendor portal (future-friendly fields only).
- Multi-company/branch tenancy beyond optional `Outlet` FK.
- Photo/file upload pipeline in v1 (notes text only; media can follow later).

## Decisions

### 1. New app `assets` (not `inventory/`, not inside `meals`)

- **Choice:** Create `assets` with standard layout (`models`, `api/`, `services/`, `filters`, `tests/`, `docs/`).
- **Why:** Empty `inventory/` implies consumable stock; `meals` owns food costing. Permanent assets are a separate bounded context.
- **Alternatives:** Fill `inventory/` (rejected—name collision with future stock); put models under `business` (rejected—business is profile/outlet, not equipment).

### 2. Two resources: `AssetCategory` + `PermanentAsset`

- **Choice:**
  - `AssetCategory`: name (unique), slug or code, description, `is_active`, timestamps, `public_id`.
  - `PermanentAsset`: name, category FK, unique `asset_tag`, optional serial/brand/model, `status`, optional `outlet`, `quantity` (≥1), purchase_date, purchase_cost (Decimal), currency default `BDT`, warranty_until, notes, `is_active`, timestamps, `public_id`.
- **Why:** Categories keep the admin UI filterable (Kitchen Equipment, Furniture, Computer, Lights, Other) while each record tracks a countable unit or a homogeneous batch via `quantity`.
- **Alternatives:** Flat enum-only categories (rejected—admins cannot add “Large korai” style groupings without deploy); one-row-per-SKU with no quantity (awkward for identical chairs).

### 3. Status lifecycle (string enums)

Allowed values:

| Status | Meaning |
|--------|---------|
| `in_service` | Actively used |
| `under_maintenance` | Temporarily out of normal use |
| `retired` | No longer used; kept for history |
| `disposed` | Sold, scrapped, or written off |

- Transitions are free-form in v1 (admin may set any status) but serializers/services validate membership in the allowlist.
- Soft deactivate: `is_active=false` hides from default lists; status `retired`/`disposed` recommended when retiring. `DELETE` soft-retires (`is_active=false`, status → `retired` if still `in_service` / `under_maintenance`) rather than hard-deleting, preserving auditability. Hard delete only via Django Admin / superuser optional later—not exposed on the public admin REST delete.

### 4. Identity and API shape

- Integer PK internally; `PublicIdMixin.public_id` for all client paths and payloads.
- Mount: `/assets/categories/` and `/assets/` (or `/assets/items/`) — prefer:
  - `GET|POST /assets/categories/`
  - `GET|PATCH|DELETE /assets/categories/{public_id}/`
  - `GET|POST /assets/`
  - `GET|PATCH|DELETE /assets/{public_id}/`
- Permissions: `IsVerifiedAdmin` on all endpoints (no anonymous list).
- Pagination: page size default 50, max 200 (match notices/ingredients admin).
- Money: `purchase_cost` as Decimal in DB; serialize as string; never float.
- Nested refs: `category_public_id`, `outlet_public_id` (if Outlet has/gets public_id)—**Decision:** Outlet today may only expose integer id on admin filters. Use optional write field `outlet_id` (integer PK) **or** add Outlet `public_id` only if already available. Prefer **optional integer `outlet` PK on write for v1** with read nested `{ id, name }` to avoid blocking on Outlet UUID migration; document as admin-only. If project public-UUID rule applies to new nested refs, expose `outlet_id` as write-only integer for verified admin (admin surfaces already use integer outlet elsewhere) and note future `outlet_public_id` alignment.

### 5. Seed default categories

Management command or migration data: Kitchen Equipment, Furniture, Lighting, Computer Equipment, Other. Admins may add more.

### 6. Services layer

- `assets/services/catalog.py`: create/update/retire helpers, tag uniqueness normalization (trim/uppercase optional), status validation, default list queryset (`is_active=true` unless `include_inactive=true`).
- Views stay thin; no business rules in serializers beyond field validation + `full_clean()`.

### 7. Separation from food inventory

- No FK to `Ingredient`, `MealCycle`, or `Order`.
- Docs and OpenAPI descriptions MUST state assets are non-consumable and never deducted by cooking.
- Do not mount under `/meals/`.

### 8. Docs

- `assets/docs/frontend/permanent-asset-admin.md` — full workflow, auth, every field, examples.
- `assets/docs/backend/permanent-asset-management.md` — models, rules, verification.

## Risks / Trade-offs

- **[Risk] Confusion with future consumable inventory** → Mitigation: app named `assets`; docs/OpenAPI explicitly say permanent/non-consumable; leave `inventory/` unused.
- **[Risk] Quantity vs individual tagging** → Mitigation: support both (`quantity` default 1); recommend unique `asset_tag` per physical high-value unit; allow quantity > 1 for homogeneous low-value batches (e.g. chairs) with one tag for the batch.
- **[Risk] Soft-delete surprises for admin UI** → Mitigation: document DELETE as retire; list defaults to active; filter `status` and `include_inactive`.
- **[Risk] Outlet without public_id** → Mitigation: v1 uses optional integer outlet FK for admin-only API; follow-up can add `outlet_public_id` when business resources get UUIDs.
- **[Trade-off] No maintenance work-order module** → Status `under_maintenance` is a flag only; richer WO tracking deferred.

## Migration Plan

1. Add app + models + migrations (including seed categories).
2. Wire URLs and permissions; ship OpenAPI.
3. Deploy; no data backfill required (greenfield).
4. Frontend admin integrates against docs.
5. Rollback: unmount URLs and remove app from `INSTALLED_APPS` if needed; drop tables only if no production data retained.

## Open Questions

- None blocking for v1. Optional later: asset photos, assignment to staff, maintenance tickets, barcode/QR labels tied to `asset_tag`.
