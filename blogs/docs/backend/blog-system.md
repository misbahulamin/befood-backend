# Backend — Blog System

## Quick summary

Verified admins manage blog **categories** and **articles** (title, content, cover image, publish state). The public website lists published articles, opens detail pages (with view tracking), shows most-popular articles, and suggests related articles.

| Audience | Method | Path | Auth |
|----------|--------|------|------|
| Public list | `GET` | `/blogs/public/` | None |
| Public detail | `GET` | `/blogs/public/{public_id}/` | None (increments `view_count`) |
| Most popular | `GET` | `/blogs/public/popular/` | None |
| Related | `GET` | `/blogs/public/{public_id}/related/` | None |
| Admin categories | `GET\|POST` | `/blogs/categories/` | Token + verified admin |
| Admin category detail | `GET\|PATCH\|DELETE` | `/blogs/categories/{public_id}/` | Token + verified admin |
| Admin articles | `GET\|POST` | `/blogs/articles/` | Token + verified admin |
| Admin article detail | `GET\|PATCH\|DELETE` | `/blogs/articles/{public_id}/` | Token + verified admin |

## Permissions

| Actor | Admin CRUD | Public endpoints |
|-------|------------|------------------|
| Anonymous | 401 | Allowed |
| Customer / non-admin | 403 | Allowed |
| Unverified admin | 403 | Allowed |
| Verified admin (`IsVerifiedAdmin`) | Allowed | Allowed |

## Models

### `BlogCategory`

| Field | Notes |
|-------|--------|
| `public_id` | UUID, API identity |
| `name` | Required, unique (case-insensitive at API layer) |
| `slug` | Unique; auto from name when omitted on create |
| `sort_order` | Lower first (default `0`) |
| `is_active` | Default `true` |

Delete uses `SET_NULL` on articles: deleting a category clears `article.category`.

### `BlogArticle`

| Field | Notes |
|-------|--------|
| `public_id` | UUID, API identity |
| `category` | Nullable FK → `BlogCategory`, `on_delete=SET_NULL` |
| `author` | FK → `User`, `PROTECT`; set from `request.user` on create |
| `title` / `slug` / `content` | Required; slug auto from title when omitted |
| `excerpt` | Optional card summary |
| `cover_image` | Optional on draft; **required when publishing** |
| `cover_image_title` | Optional alt / image title |
| `is_published` | Default `false` |
| `published_at` | Set once on first publish (UTC); kept on unpublish |
| `view_count` | Monotonic counter; incremented on public detail only |

Indexes support public list (`is_published`, `published_at`), popular (`is_published`, `view_count`), and related (`category`, `is_published`).

## Publish rules

1. Create defaults: draft (`is_published=false`), `published_at=null`, `view_count=0`, `author=request.user`.
2. First transition to `is_published=true` with a cover image sets `published_at=timezone.now()` (UTC).
3. Publishing without a cover image → validation error (`400`).
4. Unpublish keeps historical `published_at`.
5. Clients cannot set or change `author`.

## View / popular / related logic

- **Views:** On successful public detail of a published article, `view_count` is updated with `F('view_count') + 1`. No increment on list, popular, related, or admin.
- **Popular:** Published only; order `-view_count`, `-published_at`, `-id`; `limit` default 5, max 20 (clamped). Non-paginated list.
- **Related:** Exclude source. Prefer same-category published articles (same ordering), then backfill from all published. If source has no category, use global backfill only. `limit` default 4, max 12 (clamped). Unpublished / missing source → `404`.

## Public payload notes

- Client IDs are `public_id` only (no integer `id`).
- List / popular / related omit full `content` (card shape).
- Detail includes `content`.
- Nested category: `{public_id, name}` when present.
- Author exposed as `author_display_name` (full name or username).

## How to verify

```bash
python manage.py test blogs.tests.test_blogs
```

Swagger: `/api/docs/` — tags **Public Blogs**, **Admin Blog Categories**, **Admin Blog Articles**.
