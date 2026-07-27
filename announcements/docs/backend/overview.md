# Backend — Announcements / Promotion Popups

Promotional banners and notice popups with three surfaces:

| Surface | Who | How |
|---------|-----|-----|
| Admin REST API | Verified admins | Token auth CRUD at `/announcements/` |
| Django Admin | Staff | `/admin/announcements/announcement/` (alternate UI) |
| Public active feed | Website visitors | Unauthenticated `GET /announcements/active/` |

**Not the same as site notices.** Use `/notices/` for bilingual operational alerts. Use `/announcements/` for typed popups with optional image + CTA.

## Quick summary

| Concern | Detail |
|---------|--------|
| App | `announcements` |
| Admin API | `IsVerifiedAdmin` on `/announcements/` |
| Public API | `GET /announcements/active/` — no auth |
| Identity | `public_id` (UUID); integer PK internal only |

## Key model fields

| Field | Meaning |
|-------|---------|
| `public_id` | Stable API id (UUID) |
| `title` | Required title |
| `description` | Optional body text |
| `type` | `notice` \| `offer` \| `new_package` \| `maintenance` \| `announcement` |
| `severity` | `info` \| `warning` \| `success` \| `error` |
| `image` | Optional banner image |
| `button_text` | Optional CTA label |
| `button_url` | Optional CTA URL (required if `button_text` is set) |
| `is_published` | Publish toggle (`false` = draft) |
| `publish_at` | Optional start (UTC). Null = immediately eligible when published |
| `publish_until` | Optional end (UTC), **inclusive**. Null = no automatic expiry |
| `priority` | Higher appears first on the public feed |

Admin API responses also include read-only `lifecycle_status`
(`draft` \| `scheduled` \| `active` \| `expired`) and timestamps.

## Active rule (computed)

An announcement is **active** at time `now` (UTC) when all hold:

1. `is_published` is `true`
2. `publish_at` is null **or** `publish_at <= now`
3. `publish_until` is null **or** `publish_until >= now` (inclusive)

Expiry does **not** flip `is_published`. The public feed simply omits expired rows.
Service: `announcements.services.get_active_announcements(at=None)`.

Ordering: `-priority`, `-created_at`, `-id`.

**Difference from notices:** notices use exclusive end (`publish_until > now`). Announcements use inclusive end (`>=`).

## Admin publish workflow (REST)

1. `POST /announcements/` with `is_published=false` → draft (not on public feed).
2. Optionally set schedule, image (multipart), CTA.
3. `PATCH /announcements/{public_id}/` with `is_published=true` → eligible when the window includes now.
4. To hide early: `PATCH` with `is_published=false`.
5. `DELETE /announcements/{public_id}/` for permanent removal.

## Admin endpoints

```http
GET|POST          /announcements/
GET|PATCH|DELETE  /announcements/{public_id}/
```

- Auth: `Authorization: Token <admin_token>` + `IsVerifiedAdmin`
- Filters: `is_published`, `type`, `severity`, `search`
- Pagination: `page`, `page_size` (default 50, max 200)
- Ordering: `priority`, `publish_at`, `created_at`, `updated_at`
- Image: `multipart/form-data` on create/patch when uploading

See [`../frontend/announcements-admin.md`](../frontend/announcements-admin.md).

## Public endpoint

```http
GET /announcements/active/
```

- Auth: none (`AllowAny`; no `Authorization` header)
- Pagination: `page`, `page_size` (default 20, max 50)
- Ordering: priority DESC, newest first

See [`../frontend/announcements-public.md`](../frontend/announcements-public.md).

## Validation rules

- Reject blank `title`.
- Reject if `publish_until <= publish_at` when both are set.
- Reject `button_text` without a valid `button_url`.
- `type` / `severity` must be allowlisted choices.
- Optional images: jpg/jpeg/png/webp, max 5MB.
- Admin writes call model `full_clean()`.

## How to verify

```bash
python manage.py migrate announcements
python manage.py test announcements.tests.test_announcements
```

Create/publish via admin API, then call `GET /announcements/active/` without a token.
