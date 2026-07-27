# Backend — Site Notices

Site-wide bilingual announcements with three management/read surfaces:

| Surface | Who | How |
|---------|-----|-----|
| Admin REST API | Verified admins | Token auth CRUD at `/notices/` |
| Django Admin | Staff | `/admin/notices/notice/` (alternate UI) |
| Public active feed | Website visitors | Unauthenticated `GET /notices/active/` |

## Quick summary

| Concern | Detail |
|---------|--------|
| App | `notices` |
| Admin API | `IsVerifiedAdmin` on `/notices/` (list/create/retrieve/patch/delete) |
| Django Admin | `/admin/notices/notice/` |
| Public API | `GET /notices/active/` — no auth |
| Identity | `public_id` (UUID); integer PK internal only |

## Key model fields

| Field | Meaning |
|-------|---------|
| `public_id` | Stable API id (UUID) |
| `title_en` / `title_bn` | Titles; **at least one** required |
| `body_en` / `body_bn` | Plain-text bodies (optional per locale) |
| `severity` | `info` \| `warning` \| `critical` (UI hint) |
| `is_published` | Publish toggle (`false` = draft) |
| `publish_at` | Optional start (UTC). Null = immediately eligible when published |
| `publish_until` | Optional end (UTC). Null = no automatic expiry |
| `sort_order` | Lower appears first on the public feed |

Admin API responses also include read-only `lifecycle_status`
(`draft` \| `scheduled` \| `active` \| `expired`) and timestamps.

## Active rule (computed)

A notice is **active** at time `now` (UTC) when all hold:

1. `is_published` is `true`
2. `publish_at` is null **or** `publish_at <= now`
3. `publish_until` is null **or** `publish_until > now`

Expiry does **not** flip `is_published`. The public feed simply omits expired rows.
Service: `notices.services.get_active_notices(at=None)`.

Lifecycle labels: `draft` | `scheduled` | `active` | `expired`
(`notices.services.compute_lifecycle_status`).

## Admin publish workflow (REST)

1. `POST /notices/` with titles and `is_published=false` → draft (not on public feed).
2. Optionally set `publish_at` / `publish_until`.
3. `PATCH /notices/{public_id}/` with `is_published=true` → eligible for the public feed when the schedule window includes now.
4. To hide early: `PATCH` with `is_published=false`.
5. `DELETE /notices/{public_id}/` for permanent removal (prefer unpublish for temporary hide).

Django Admin remains available for the same model and validation rules.

## Admin endpoints

```http
GET|POST          /notices/
GET|PATCH|DELETE  /notices/{public_id}/
```

- Auth: `Authorization: Token <admin_token>` + `IsVerifiedAdmin`
- Filters: `is_published`, `severity`, `search` (titles/bodies)
- Pagination: `page`, `page_size` (default 50, max 200)
- Ordering: `sort_order`, `publish_at`, `created_at`, `updated_at`

See [`../frontend/site-notices-admin.md`](../frontend/site-notices-admin.md).

## Public endpoint

```http
GET /notices/active/
```

- Auth: none (`AllowAny`; no `Authorization` header)
- Pagination: `page`, `page_size` (default 20, max 50)
- Ordering: `sort_order` ASC, then `-publish_at`, `-created_at`, `-id`

See [`../frontend/site-notices.md`](../frontend/site-notices.md) for JSON examples and visitor UI guidance.

## Validation rules

- Reject save if both titles are blank.
- Reject if `publish_until <= publish_at` when both are set.
- `severity` must be one of the allowlisted choices.
- Admin writes call model `full_clean()` so REST and Django Admin share the same rules.

## How to verify

```bash
python manage.py migrate notices
python manage.py test notices.tests.test_notices
```

Create/publish via admin API or Django Admin, then call `GET /notices/active/` without a token.
