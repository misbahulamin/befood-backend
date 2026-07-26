## Context

`public-site-notices` shipped the `Notice` model, Django Admin, `get_active_notices`, and public `GET /notices/active/` (`AllowAny`). Verified admins already manage meals and ingredients via token + `IsVerifiedAdmin` ViewSets. The web admin UI needs the same CRUD surface for notices so operators never leave the management frontend.

Stakeholders: verified admins (CRUD), website visitors (unchanged public feed), frontend web admin.

Constraints: reuse existing `Notice` model and validation; keep public feed lean and unauthenticated; follow ingredient/inventory admin API conventions (`public_id` lookup, pagination, OpenAPI).

## Goals / Non-Goals

**Goals:**

- Add admin REST CRUD for notices under `/notices/` with `IsVerifiedAdmin`.
- Support list filters (`is_published`, `severity`, search), deterministic ordering, pagination.
- Expose full admin fields including `is_published`, schedule window, and a read-only computed `lifecycle_status` (`draft` | `scheduled` | `active` | `expired`).
- Call `full_clean()` / model `clean()` on write so API and Admin share validation.
- Document the admin API for the web frontend; leave public feed docs intact.

**Non-Goals:**

- Changing the public active-feed contract or auth.
- Removing Django Admin.
- Soft-delete / archive workflow beyond hard delete + unpublish.
- Multi-tenant or per-branch notices.

## Decisions

### 1. Route layout: admin collection at `/notices/` + keep `/notices/active/`

```text
GET|POST          /notices/                    IsVerifiedAdmin
GET|PATCH|DELETE  /notices/{public_id}/        IsVerifiedAdmin
GET               /notices/active/             AllowAny (existing)
```

Register admin ViewSet as `''` or `'admin'` basename carefully so it does not collide with `active`. Prefer router register of empty prefix only if DRF routes resolve correctly; safer pattern used by other apps: register admin as the root resource name:

```text
router.register('', NoticeAdminViewSet, basename='notice')  # risky with 'active'
```

**Chosen approach:** register admin collection as `''` is ambiguous. Instead:

```text
# Keep active as today
router.register('active', ActiveNoticeViewSet, basename='active')
# Admin CRUD at /notices/notices/ OR mount admin at root with basename that
# does not steal 'active'
```

**Preferred (ingredient-style, clear):**

```text
/notices/active/     public feed (existing)
/notices/manage/     admin CRUD  — OR —
/notices/            admin list/create if we use a custom URLConf
```

**Final choice:** Mount admin ViewSet at `/notices/` via explicit paths or register with an empty basename that lists at `/notices/` while `active` remains a sibling registered path. In DRF `DefaultRouter`, more specific `active/` is registered first so `active` is not treated as a `public_id`. Pattern:

```python
router.register('active', ActiveNoticeViewSet, basename='active')
router.register('', NoticeViewSet, basename='notices')
```

Order: register `active` **before** the empty prefix so `/notices/active/` stays the public list.  
**Why:** Matches user expectation (“like ingredients at `/meals/ingredients/`”) while keeping a short `/notices/` admin collection.  
**Alternatives:** `/notices/manage/` — clearer separation, longer paths; acceptable fallback if empty-prefix routing is awkward in practice.

### 2. Permission: `IsVerifiedAdmin` only

Same class as `IngredientViewSet` / inventory. Anonymous and customers get `401`/`403`. Public feed keeps `AllowAny` + empty `authentication_classes`.  
**Why:** Consistency with existing admin APIs.

### 3. Serializer: admin vs public

- **Public** (existing): lean fields, no `is_published` / lifecycle.
- **Admin:** bilingual fields, `severity`, `is_published`, `publish_at`, `publish_until`, `sort_order`, `public_id`, timestamps, read-only `lifecycle_status` from `compute_lifecycle_status`.

Writes run model `full_clean()` (via serializer `validate` / service create-update helpers) so title and schedule rules match Admin.

### 4. Filters and pagination

`django_filters`: `is_published`, `severity`; optional `search` on titles/bodies. Pagination: same style as public notices or inventory (default ~20–50, max 200). Ordering: `sort_order`, `publish_at`, `created_at`, `updated_at`.

### 5. Delete semantics

Hard delete allowed (notices have no dependent ledger). Prefer documenting unpublish (`is_published=false`) for soft hide; delete for permanent removal.

### 6. Docs

Extend `notices/docs/frontend/site-notices.md` (or add `site-notices-admin.md`) with admin endpoint grid, Token auth, examples. Backend overview notes dual surfaces (Admin UI + REST).

## Risks / Trade-offs

- **[Risk] Empty-prefix router collides with `active`** → Mitigation: register `active` first; add URL resolution tests; fall back to `/notices/manage/` if needed.
- **[Risk] Admins confuse public vs admin list payloads** → Mitigation: separate serializers; docs emphasize auth and field differences.
- **[Trade-off] Hard delete** → Simple; no soft-delete table. Unpublish covers temporary hide.

## Migration Plan

1. Add admin serializer, filters, ViewSet, URL registration (no model migration expected).
2. Tests for auth denial, CRUD, validation, filters.
3. Docs update; deploy.
4. Rollback: remove admin routes; model and public feed remain.

## Open Questions

- None blocking. Prefer `/notices/` + `/notices/active/` as above; switch to `/notices/manage/` only if routing tests fail.
