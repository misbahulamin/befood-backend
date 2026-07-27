# Permanent Asset Admin API (Frontend)

Verified-admin management of **permanent (non-consumable)** kitchen and office equipment — refrigerators, burners, cookware, furniture, lights, computers, and similar items.

These assets are **not** food inventory. Quantity never decreases through cooking, meal costing, or orders.

**Target client:** Frontend admin (web) only. No public or mobile endpoints.

---

## Auth

| Item | Value |
|------|--------|
| Header | `Authorization: Token <token>` |
| Who | Active user who is **superuser** OR (`AdminProfile.is_verified=true` + group `ADMIN`) |
| Permission | `IsVerifiedAdmin` on every endpoint below |

Login via existing admin auth (`user_management` admin login), then use the returned token.

Unauthorized → `401`. Authenticated but not verified admin → `403`.

---

## Endpoint grid

Base path: `/assets/`

### Categories

| Method | Path | Why |
|--------|------|-----|
| `GET` | `/assets/categories/` | List categories (paginated) |
| `POST` | `/assets/categories/` | Create a category |
| `GET` | `/assets/categories/{public_id}/` | Category detail |
| `PATCH` | `/assets/categories/{public_id}/` | Partial update |
| `DELETE` | `/assets/categories/{public_id}/` | Soft-deactivate (`is_active=false`) |

### Permanent assets

| Method | Path | Why |
|--------|------|-----|
| `GET` | `/assets/` | List assets (paginated; active only by default) |
| `POST` | `/assets/` | Register a new permanent asset |
| `GET` | `/assets/{public_id}/` | Asset detail |
| `PATCH` | `/assets/{public_id}/` | Partial update (status, location, notes, …) |
| `DELETE` | `/assets/{public_id}/` | Soft-retire (keeps history) |

All list/detail URLs use opaque UUID `public_id` — never integer PK in paths.

---

## Recommended UI workflow

1. **Login** as verified admin → store Token.
2. **Load categories** — `GET /assets/categories/` (seeds include Kitchen Equipment, Furniture, Lighting, Computer Equipment, Other).
3. **Optionally create category** — e.g. “Large Cookware” via `POST /assets/categories/`.
4. **Register assets** — `POST /assets/` with `category_public_id` + unique `asset_tag`.
5. **Browse / filter** — `GET /assets/?status=in_service&search=REF`.
6. **Update status** — `PATCH` to `under_maintenance` when being repaired.
7. **Retire** — `DELETE /assets/{public_id}/` (soft). Use `include_inactive=true` to see retired rows later.

Call categories first when building create/edit forms so the category dropdown has `public_id` values.

---

## Status glossary

| Value | Meaning | UI hint |
|-------|---------|---------|
| `in_service` | Actively used | Default for new assets |
| `under_maintenance` | Temporarily out of normal use | Show maintenance badge |
| `retired` | No longer used; kept for history | Usually also `is_active=false` after DELETE |
| `disposed` | Sold / scrapped / written off | Historical only |

`DELETE` on an asset: sets `is_active=false`. If status was `in_service` or `under_maintenance`, status becomes `retired`. If already `disposed` / `retired`, status is left as-is.

`DELETE` on a category: only sets `is_active=false` (does not hard-delete).

---

## Category fields

| Field | Type | Read/Write | Meaning |
|-------|------|------------|---------|
| `public_id` | UUID string | read | Opaque id for URLs |
| `name` | string | R/W | Unique category name |
| `description` | string | R/W | Optional help text |
| `is_active` | bool | R/W | Soft flag; default list hides inactive |
| `created_at` | datetime (UTC) | read | Created |
| `updated_at` | datetime (UTC) | read | Last update |

### Create category — example

```http
POST /assets/categories/
Authorization: Token <token>
Content-Type: application/json

{
  "name": "Large Cookware",
  "description": "Korai and similar large pans"
}
```

```json
{
  "public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Large Cookware",
  "description": "Korai and similar large pans",
  "is_active": true,
  "created_at": "2026-07-27T07:00:00Z",
  "updated_at": "2026-07-27T07:00:00Z"
}
```

---

## Permanent asset fields

| Field | Type | Read/Write | Meaning |
|-------|------|------------|---------|
| `public_id` | UUID string | read | Opaque id for URLs |
| `name` | string | R/W | Display name (e.g. Walk-in Refrigerator) |
| `category_public_id` | UUID | **write only** | Category to attach (must be active) |
| `category` | object `{public_id, name}` | read | Nested category summary |
| `asset_tag` | string | R/W | Unique physical label/code (required) |
| `status` | enum string | R/W | See status glossary |
| `quantity` | int ≥ 1 | R/W | `1` for a single tagged unit; `>1` for identical batch (e.g. 12 chairs) |
| `serial_number` | string | R/W | Optional manufacturer serial |
| `brand` | string | R/W | Optional brand |
| `model` | string | R/W | Optional model |
| `outlet_id` | int or null | **write only** | Optional outlet PK (admin-only integer for v1) |
| `outlet` | object `{id, name}` or null | read | Nested outlet summary |
| `purchase_date` | date `YYYY-MM-DD` or null | R/W | Optional |
| `purchase_cost` | decimal **string** or null | R/W | Exact money, e.g. `"45000.00"` — never float |
| `currency` | 3-letter string | R/W | Default `BDT` |
| `warranty_until` | date or null | R/W | Must not be before `purchase_date` if both set |
| `notes` | string | R/W | Free text |
| `is_active` | bool | R/W | Soft flag; default list hides inactive |
| `created_at` | datetime | read | |
| `updated_at` | datetime | read | |

### Create refrigerator — example

```http
POST /assets/
Authorization: Token <token>
Content-Type: application/json

{
  "name": "Walk-in Refrigerator",
  "category_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "asset_tag": "KE-REF-001",
  "status": "in_service",
  "quantity": 1,
  "brand": "Samsung",
  "outlet_id": 1,
  "purchase_date": "2026-01-15",
  "purchase_cost": "45000.00",
  "currency": "BDT",
  "notes": "Main kitchen cold storage"
}
```

### Batch of chairs — example

```json
{
  "name": "Dining Chairs",
  "category_public_id": "…",
  "asset_tag": "FU-CHAIR-BATCH-1",
  "quantity": 12,
  "status": "in_service"
}
```

### Patch status — example

```http
PATCH /assets/{public_id}/
Authorization: Token <token>
Content-Type: application/json

{ "status": "under_maintenance" }
```

### Soft-retire — example

```http
DELETE /assets/{public_id}/
Authorization: Token <token>
```

→ `204 No Content`. Row remains in DB with `is_active=false`.

---

## List query parameters (assets)

| Param | Meaning |
|-------|---------|
| `status` | `in_service` \| `under_maintenance` \| `retired` \| `disposed` |
| `category_public_id` | UUID of category |
| `outlet` | Outlet integer PK |
| `is_active` | `true` / `false` |
| `include_inactive` | `true` to include soft-retired rows (default: active only) |
| `search` | Case-insensitive match on name, asset_tag, serial_number, brand, model |
| `ordering` | `name`, `asset_tag`, `status`, `created_at`, `updated_at` (prefix `-` for desc) |
| `page` | Page number (1-based) |
| `page_size` | Default **50**, max **200** |

Category list supports: `is_active`, `include_inactive`, `search`, `ordering`, `page`, `page_size`.

Paginated response shape:

```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": [ /* asset objects */ ]
}
```

---

## Errors (typical)

| Situation | Status |
|-----------|--------|
| Missing / bad token | `401` |
| Customer / unverified admin | `403` |
| Unknown `public_id` | `404` |
| Duplicate `asset_tag` or category `name` | `400` |
| Invalid `status`, `quantity` &lt; 1, warranty before purchase, missing category | `400` |
| Inactive/missing `category_public_id` | `400` |

Field errors arrive in the project’s standard validation error body (field → list of messages).

---

## Non-consumable boundary (must not mix in UI)

- Do **not** show these assets inside food/ingredient stock screens.
- Do **not** deduct `quantity` when meals are cooked or orders are fulfilled.
- Ingredient catalog (`/meals/ingredients/`) remains a separate costing catalog.

---

## How to verify quickly

1. Open `/api/docs/` → tag **Admin Permanent Assets**.
2. Authorize with Token.
3. `GET /assets/categories/` → see seeded categories.
4. `POST /assets/` → create one asset; `DELETE` it; confirm `GET /assets/?include_inactive=true` still shows it.
5. Automated: `python manage.py test assets.tests.test_assets`
