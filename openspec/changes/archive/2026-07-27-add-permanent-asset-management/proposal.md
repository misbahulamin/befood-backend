## Why

BEFOOD kitchens and offices rely on durable, non-consumable equipment (refrigerators, burners, korai, rice cookers, furniture, lights, computers, and similar items), but the backend only models meal packages, ingredients for costing, and orders. There is no place to register, locate, or retire these permanent assets, so staff cannot inventory equipment in the frontend admin without mixing them into food-related catalogs. We need a dedicated Permanent Asset Management module—clearly separate from meal/ingredient stock—so verified admins can track what the business owns without implying cooking consumption.

## What Changes

- Add a new Django app `assets` for Permanent Asset Management (do not reuse empty `inventory/` or extend `Ingredient`).
- Introduce **asset categories** (kitchen equipment, furniture, computer equipment, lights, other) and **individual permanent asset records** with opaque `public_id`, asset tag, optional serial/brand/model, status lifecycle, optional outlet location, purchase metadata, and notes.
- Expose a **verified-admin-only** REST API under `/assets/` for frontend admin CRUD (list/filter/search/paginate, create, retrieve, patch, soft-retire or delete per design), gated by `IsVerifiedAdmin` (Token auth).
- Enforce hard domain boundary: permanent assets MUST NEVER participate in meal costing, recipe deduction, order fulfillment, or food inventory quantity changes.
- Ship OpenAPI annotations, automated API tests, and frontend/backend docs so the admin UI can integrate without guessing the contract.
- No customer/public feed and no mobile operator endpoints in this change (admin management UI only).

## Capabilities

### New Capabilities
- `permanent-asset-catalog`: Domain model for categories and permanent assets—identity, classification, status lifecycle, location (optional outlet), purchase/warranty metadata, validation rules, and explicit separation from food/ingredient inventory.
- `permanent-asset-admin-api`: Token-authenticated verified-admin HTTP CRUD, filters, search, pagination, OpenAPI, and admin documentation for the frontend admin app.

### Modified Capabilities
- (none — no existing `openspec/specs/` capability covers fixed/permanent assets)

## Impact

- **New app:** `assets/` (models, services, api, filters, admin, tests, docs).
- **Wiring:** `INSTALLED_APPS`, `core/urls.py` mount at `/assets/`.
- **Depends on:** `core.PublicIdMixin`, `user_management` `IsVerifiedAdmin`, optional `business.Outlet` for location.
- **Does not change:** `meals.Ingredient`, meal cycles, orders, notices, announcements, or any food stock behavior.
- **Clients:** Frontend admin (verified `ADMIN` / superuser) only; storefront and riders unaffected.
- **Risk:** Low coupling if boundary is kept; avoid naming confusion with future consumable inventory if/when that module ships under a different app.
