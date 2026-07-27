## 1. App scaffold and models

- [x] 1.1 Create Django app `assets` with standard layout (`models.py`, `admin.py`, `filters.py`, `apps.py`, `api/`, `services/`, `tests/`, `docs/frontend/`, `docs/backend/`)
- [x] 1.2 Implement `AssetCategory` model (`PublicIdMixin`, unique name, description, `is_active`, timestamps) and `PermanentAsset` model (category FK, unique `asset_tag`, status allowlist, quantity ≥ 1, optional serial/brand/model/outlet/purchase/warranty/notes, `is_active`, timestamps)
- [x] 1.3 Add model `clean()` validation (quantity, status allowlist, warranty vs purchase_date) and useful indexes (`asset_tag`, `status`, `is_active`)
- [x] 1.4 Register models in Django Admin; add app to `INSTALLED_APPS`; create and apply migrations
- [x] 1.5 Seed default categories (Kitchen Equipment, Furniture, Lighting, Computer Equipment, Other) via data migration or management command

## 2. Domain services

- [x] 2.1 Implement `assets/services/catalog.py` helpers for category create/update/deactivate and asset create/update/soft-retire (normalize tag, enforce uniqueness, default active queryset)
- [x] 2.2 Ensure services never reference meal/ingredient/order modules and keep business logic out of views

## 3. Admin API — categories

- [x] 3.1 Implement category serializers (read/write), filters, and `AssetCategoryViewSet` with `IsVerifiedAdmin`, `lookup_field='public_id'`, pagination
- [x] 3.2 Wire `/assets/categories/` routes (list/create/retrieve/partial_update/destroy-as-soft-deactivate)
- [x] 3.3 Add OpenAPI `@extend_schema` / `@extend_schema_view` for category endpoints

## 4. Admin API — permanent assets

- [x] 4.1 Implement permanent asset serializers accepting `category_public_id`, optional outlet reference, decimal `purchase_cost` as string; expose nested category summary on read
- [x] 4.2 Implement `PermanentAssetViewSet` with `IsVerifiedAdmin`, `lookup_field='public_id'`, filters (`status`, category, `is_active`/`include_inactive`, outlet), search, ordering, pagination (default 50, max 200)
- [x] 4.3 Soft-retire on DELETE (`is_active=false`; set status to `retired` when leaving `in_service`/`under_maintenance`)
- [x] 4.4 Mount `/assets/` in `assets/api/urls.py` and include from `core/urls.py`
- [x] 4.5 Add OpenAPI annotations for asset endpoints including status enum and non-consumable description

## 5. Tests

- [x] 5.1 Category API tests: verified admin CRUD success; anonymous/non-admin/unverified admin denied; duplicate name rejected
- [x] 5.2 Asset API tests: create refrigerator-style asset; batch quantity; duplicate `asset_tag`; invalid status/quantity; warranty before purchase; filter/search/pagination; default excludes inactive; DELETE soft-retires
- [x] 5.3 Permission matrix coverage for all mutating and list endpoints using Token + verified `AdminProfile` + `ADMIN` group helpers matching existing notice/ingredient tests

## 6. Documentation

- [x] 6.1 Write `assets/docs/frontend/permanent-asset-admin.md` with auth, endpoint grid, full workflows, every field meaning, query params, status glossary, error examples, and non-consumable boundary note
- [x] 6.2 Write `assets/docs/backend/permanent-asset-management.md` with models, validation rules, soft-retire behavior, and how to verify (Swagger + tests)

## 7. Verification

- [x] 7.1 Run asset-focused test suite and fix failures
- [x] 7.2 Spot-check OpenAPI schema / `/api/docs/` for `/assets/` and `/assets/categories/` visibility and auth
