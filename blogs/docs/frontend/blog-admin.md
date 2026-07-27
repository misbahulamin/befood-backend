# Frontend — Blog Admin

Backend overview: [`../backend/blog-system.md`](../backend/blog-system.md).

Public website feed: [`blog-public.md`](blog-public.md).

## What to build

Admin UI to:

1. Create / edit / deactivate blog **categories**.
2. Create / edit / publish blog **articles** with optional category and cover image.
3. Never show drafts on the public site until `is_published=true` **and** a cover image is present.

Target client: **web admin**.

## Auth

```http
Authorization: Token <admin_token>
```

Caller must be a **verified admin**. Customers and unverified admins receive `403`.

## Recommended workflow

1. `POST /blogs/categories/` — create section (`name`; optional `slug`, `sort_order`).
2. `POST /blogs/articles/` — create draft (`title`, `content`; optional `category_public_id`, `excerpt`). Author is set automatically.
3. Upload cover via `PATCH /blogs/articles/{public_id}/` with `multipart/form-data` (`cover_image`, optional `cover_image_title`).
4. `PATCH` with `is_published=true` when ready (requires cover).
5. Confirm on `GET /blogs/public/` (no auth) that the item appears.

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| List categories | GET | `/blogs/categories/` |
| Create category | POST | `/blogs/categories/` |
| Update category | PATCH | `/blogs/categories/{public_id}/` |
| Delete category | DELETE | `/blogs/categories/{public_id}/` |
| List articles | GET | `/blogs/articles/?category_public_id=&is_published=&search=` |
| Create article | POST | `/blogs/articles/` |
| Publish / edit | PATCH | `/blogs/articles/{public_id}/` |
| Delete article | DELETE | `/blogs/articles/{public_id}/` |

Admin lists are paginated (default `page_size=50`, max `200`).

## Create category example

```http
POST /blogs/categories/
Authorization: Token <token>
Content-Type: application/json

{
  "name": "Nutrition Tips",
  "sort_order": 1,
  "is_active": true
}
```

Response includes `public_id` and auto-generated `slug` (`nutrition-tips`) when omitted.

## Create draft article example

```http
POST /blogs/articles/
Authorization: Token <token>
Content-Type: application/json

{
  "title": "5 Meal Prep Habits",
  "content": "<p>Full HTML or plain text body…</p>",
  "excerpt": "Quick habits for busy weeks.",
  "category_public_id": "<category-uuid>"
}
```

Notes:

- `author` is ignored if sent; server sets the authenticated admin.
- Starts as draft (`is_published=false`, `published_at=null`, `view_count=0`).
- Response includes `author_display_name` / `author_username`.

## Multipart cover + publish example

```http
PATCH /blogs/articles/{public_id}/
Authorization: Token <token>
Content-Type: multipart/form-data

cover_image: <file>
cover_image_title: Meal prep box
is_published: true
```

Publishing without a cover returns a field validation error on `cover_image`. Unpublishing later keeps the original `published_at`.

## Delete category behavior

`DELETE /blogs/categories/{public_id}/` succeeds even when articles reference it. Those articles get `category=null`. Prefer deactivating (`is_active=false`) when you want to retire a category without losing related-article signals.
