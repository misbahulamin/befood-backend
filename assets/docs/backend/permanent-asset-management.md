# Permanent Asset Management (Backend)

## Summary

Django app `assets` tracks durable, non-consumable kitchen/office equipment for verified frontend admins. It is deliberately separate from `meals.Ingredient` and any future consumable inventory.

Mounted at `/assets/` (see `core/urls.py`). Permissions: `IsVerifiedAdmin`.

## Models

### `AssetCategory`

| Field | Notes |
|-------|--------|
| `public_id` | `PublicIdMixin` UUID |
| `name` | Unique |
| `description` | Optional |
| `is_active` | Soft flag |
| `created_at` / `updated_at` | Auto |

Seeded (migration `0002_seed_categories`): Kitchen Equipment, Furniture, Lighting, Computer Equipment, Other.

### `PermanentAsset`

| Field | Notes |
|-------|--------|
| `public_id` | UUID |
| `name` | Required |
| `category` | FK `PROTECT` |
| `asset_tag` | Unique, trimmed |
| `status` | `in_service` \| `under_maintenance` \| `retired` \| `disposed` |
| `quantity` | ≥ 1 |
| `serial_number`, `brand`, `model` | Optional strings |
| `outlet` | Optional FK `business.Outlet` (`SET_NULL`) |
| `purchase_date`, `purchase_cost`, `currency` | Optional; cost is `Decimal`; default currency `BDT` |
| `warranty_until` | Optional; must not precede `purchase_date` |
| `notes` | Optional |
| `is_active` | Soft flag |

Indexes on `asset_tag`, `status`, `is_active`, and `(status, is_active)`.

## Validation rules

Enforced in model `clean()` / services (via `full_clean()`):

- Name and asset_tag required (non-blank after trim)
- Quantity ≥ 1
- Status in allowlist
- `warranty_until` ≥ `purchase_date` when both set
- Currency normalized to 3-letter uppercase (default `BDT`)

API layer maps Django `ValidationError` → DRF field errors.

## Services (`assets/services/catalog.py`)

| Function | Role |
|----------|------|
| `create_category` / `update_category` | Persist + `full_clean` |
| `soft_deactivate_category` | REST DELETE on categories |
| `create_asset` / `update_asset` | Normalize tag, persist |
| `soft_retire_asset` | REST DELETE: `is_active=false`; status → `retired` if was `in_service` / `under_maintenance` |
| `active_categories` / `active_assets` | Default list querysets |

No imports from meals, orders, or ingredients.

## Soft-retire behavior

- **Asset DELETE:** soft only; row retained.
- **Category DELETE:** soft deactivate only.
- Default list querysets exclude `is_active=false` unless `include_inactive=true` or explicit `is_active` filter.

## API layout

- `AssetCategoryViewSet` → `/assets/categories/`
- `PermanentAssetViewSet` → `/assets/`
- Router registers `categories` before `''` so the path is not parsed as a UUID.
- Pagination: page size 50, max 200.
- OpenAPI tag: **Admin Permanent Assets**.

## How to verify

```bash
python manage.py test assets.tests.test_assets
```

Swagger:

1. Run server; open `/api/docs/`.
2. Confirm paths under `/assets/` and `/assets/categories/`.
3. Authorize with verified-admin Token; exercise list/create.

Frontend contract: `assets/docs/frontend/permanent-asset-admin.md`.

OpenSpec change: `openspec/changes/add-permanent-asset-management/`.
