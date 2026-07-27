# Frontend — Public Blog

Backend overview: [`../backend/blog-system.md`](../backend/blog-system.md).

Admin CRUD: [`blog-admin.md`](blog-admin.md).

## What to build

Public website surfaces:

1. Paginated blog listing (cards).
2. Article detail page (full content).
3. “Most Popular” widget.
4. “Related articles” widget on the detail page.

No authentication. Only **published** articles appear.

## Endpoint grid

| UI action | Method | Path | Notes |
|-----------|--------|------|-------|
| List articles | GET | `/blogs/public/` | Paginated cards; no `content` |
| Article detail | GET | `/blogs/public/{public_id}/` | Includes `content`; **increments `view_count`** |
| Most popular | GET | `/blogs/public/popular/?limit=` | Non-paginated list; default limit `5`, max `20` |
| Related | GET | `/blogs/public/{public_id}/related/?limit=` | Default limit `4`, max `12`; source must be published |

Optional list filters: `category` (category `public_id`), `q` (title/excerpt search).

Public list pagination: default `page_size=20`, max `50`.

## Important side effect

Every successful detail `GET` increments that article’s `view_count` by one. Do not poll detail for background refresh if you want to avoid inflating counts. List / popular / related do **not** increment views.

## Card shape (list / popular / related)

```json
{
  "public_id": "…",
  "title": "5 Meal Prep Habits",
  "slug": "5-meal-prep-habits",
  "excerpt": "Quick habits for busy weeks.",
  "cover_image": "https://…/media/blogs/covers/…jpg",
  "cover_image_title": "Meal prep box",
  "author_display_name": "Blog Admin",
  "category": { "public_id": "…", "name": "Nutrition Tips" },
  "published_at": "2026-07-28T01:00:00Z",
  "view_count": 12
}
```

Detail adds `"content": "…"`. Integer database `id` is never returned.

## Examples

### List

```http
GET /blogs/public/?page=1&page_size=12
```

Empty published catalog → `count: 0`, `results: []`.

### Detail

```http
GET /blogs/public/{public_id}/
```

Unpublished or unknown → `404`.

### Popular

```http
GET /blogs/public/popular/?limit=5
```

Ordered by highest `view_count`, then newest `published_at`. Values above `20` are clamped.

### Related

```http
GET /blogs/public/{public_id}/related/?limit=4
```

Same-category published articles preferred, then global backfill. Source article excluded. Empty list is valid when there are no other published articles. Unpublished source → `404`.
