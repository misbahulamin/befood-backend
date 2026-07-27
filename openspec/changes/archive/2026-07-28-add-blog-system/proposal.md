## Why

BeFood’s public website needs a CMS-style blog so the team can publish articles regularly (titles, rich text, cover images, authors) without redeploying. Visitors need article listing/detail, most-popular ranking by views, and related-article suggestions while reading — capabilities the current notices/announcements apps do not provide.

## What Changes

- Create a new Django app `blogs` that owns blog categories and blog articles.
- Verified admins can create, list, update, and delete blog **categories** used to group articles and power related suggestions.
- Verified admins can create, list, update, and delete blog **articles** with title, content, cover image, cover image title (alt), publish flag, and optional category; **author** is set automatically from the authenticated admin user; **published_at** is set automatically when an article is first published.
- Each article tracks a monotonically increasing **view_count** for popularity and analytics.
- Expose verified-admin REST CRUD for categories and articles (frontend admin app; multipart upload for cover images).
- Expose **public, unauthenticated** APIs for: paginated published article list, article detail (increments view count), most-popular articles, and related articles for a given article.
- Ship backend and frontend documentation for admin and public contracts.

## Capabilities

### New Capabilities

- `blog-category-management`: Verified-admin REST CRUD for blog categories (name, slug/order, active lifecycle) used to group articles and drive related-article matching.
- `blog-article-management`: Verified-admin REST CRUD for blog articles (title, content, cover image + image title, category association, `is_published`); author and publish timestamp are system-managed; responses expose `public_id` and author display fields.
- `public-blog-feed`: Unauthenticated public list and detail of published articles only, with deterministic ordering, pagination, and view-count increment on detail reads.
- `popular-blog-articles`: Unauthenticated API returning the highest `view_count` published articles (limit/query controls) for “Most Popular” UI.
- `related-blog-articles`: Unauthenticated API that suggests related published articles for a given article (same category preferred, exclude self, fallback to recent/popular when needed).

### Modified Capabilities

- (none)

## Impact

- **New app:** `blogs` registered in `INSTALLED_APPS`; URLs mounted from `core/urls.py` (e.g. `/blogs/`).
- **Models / migrations:** `BlogCategory` and `BlogArticle` with `PublicIdMixin`; FK article → category (nullable or required — design decision); FK author → `auth.User` (`PROTECT`/`SET_NULL`); `ImageField` for cover; `view_count` integer; `is_published` + `published_at`.
- **APIs:** Admin ViewSets gated by `IsVerifiedAdmin`; public list/detail/popular/related with `AllowAny`.
- **Permissions:** Reuse `user_management.api.permissions.IsVerifiedAdmin` (same pattern as FAQs, notices, announcements).
- **Media:** Cover images stored under media upload path (same pattern as announcements/meals).
- **Docs:** `blogs/docs/backend/` and `blogs/docs/frontend/` for admin CRUD and public website integration.
- **Out of scope:** Full-text search engine, comments, likes, bilingual fields, rich HTML editor hosting, scheduled publish windows beyond `is_published` + `published_at`, per-IP view deduplication beyond a simple atomic increment (optional later), mobile-operator-specific blog routes.
