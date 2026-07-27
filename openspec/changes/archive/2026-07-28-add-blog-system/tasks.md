## 1. App scaffold and models

- [x] 1.1 Create Django app `blogs` with standard layout (`models`, `admin`, `filters`, `api/`, `services/`, `tests/`, `docs/`)
- [x] 1.2 Implement `BlogCategory` model with `PublicIdMixin`, unique `name`, unique `slug`, `sort_order`, `is_active`, timestamps
- [x] 1.3 Implement `BlogArticle` model with `PublicIdMixin`, nullable FK to `BlogCategory` (`SET_NULL`), FK `author` → `User` (`PROTECT`), `title`, unique `slug`, `excerpt`, `content`, `cover_image`, `cover_image_title`, `is_published`, `published_at`, `view_count`, timestamps, and indexes for public/popular/related queries
- [x] 1.4 Add cover image upload path helper (e.g. `blogs/covers/...`) mirroring announcements/meals patterns
- [x] 1.5 Add initial migration and register `blogs` in `INSTALLED_APPS`
- [x] 1.6 Register Django Admin for categories and articles (list filters, search, readonly author/view_count/published_at as appropriate)

## 2. Domain services

- [x] 2.1 Implement `get_public_article_queryset()` returning published articles with `select_related` for category/author
- [x] 2.2 Implement `increment_article_views(article)` using atomic `F('view_count') + 1`
- [x] 2.3 Implement `get_popular_articles(limit)` ordered by `-view_count`, `-published_at` with limit clamp (default 5, max 20)
- [x] 2.4 Implement `get_related_articles(article, limit)` with same-category preference, exclude self, global backfill, limit clamp (default 4, max 12)
- [x] 2.5 Implement publish helpers: set `published_at` on first publish; validate cover image required when publishing; keep `published_at` on unpublish

## 3. Admin category API

- [x] 3.1 Add admin category serializers (create/update/list/detail) with unique name/slug validation and auto-slug from name when omitted
- [x] 3.2 Add `BlogCategoryViewSet` (list/create/retrieve/patch/delete) with `IsVerifiedAdmin`, `lookup_field=public_id`, pagination, OpenAPI tags
- [x] 3.3 Wire `/blogs/categories/` routes

## 4. Admin article API

- [x] 4.1 Add admin article serializers supporting multipart cover upload, `category_public_id`, publish fields; set author from `request.user` on create; ignore client author overrides
- [x] 4.2 Add filters for `category_public_id` and `is_published`, plus search on title/excerpt
- [x] 4.3 Add `BlogArticleViewSet` (list/create/retrieve/patch/delete) with `IsVerifiedAdmin`, `lookup_field=public_id`, pagination, OpenAPI tags; enforce publish validation via services/serializers
- [x] 4.4 Wire `/blogs/articles/` routes and include `blogs.api.urls` in `core/urls.py` under `/blogs/`

## 5. Public blog feed API

- [x] 5.1 Add public list/detail serializers (card vs detail; omit full content on list; expose `author_display_name`, nested category `public_id`/`name`, no integer `id`)
- [x] 5.2 Add public list endpoint `GET /blogs/public/` with `AllowAny`, pagination, published-only queryset, default `-published_at` ordering
- [x] 5.3 Add public detail endpoint `GET /blogs/public/{public_id}/` with `AllowAny`; return `404` for unpublished/missing; call `increment_article_views` on success
- [x] 5.4 Add OpenAPI schema metadata for public list/detail

## 6. Popular and related APIs

- [x] 6.1 Add `GET /blogs/public/popular/` using `get_popular_articles(limit)` with `AllowAny` and card serializer
- [x] 6.2 Add `GET /blogs/public/{public_id}/related/` using `get_related_articles`; `404` when source not a published article
- [x] 6.3 Ensure route ordering so `popular` is not captured as a `public_id`
- [x] 6.4 Add OpenAPI schema metadata for popular and related endpoints

## 7. Tests

- [x] 7.1 Category API tests: verified admin CRUD; duplicate name rejected; delete nullifies article category; anonymous/non-admin/unverified denied
- [x] 7.2 Article API tests: create draft with auto author; publish sets `published_at` and requires cover; unpublish keeps `published_at`; invalid `category_public_id` rejected; filters; auth denials
- [x] 7.3 Public feed tests: no auth; drafts excluded; list omits content; detail returns content and increments `view_count`; unpublished/missing → 404; no integer `id`
- [x] 7.4 Popular tests: ordered by view_count; drafts excluded; limit clamping
- [x] 7.5 Related tests: excludes self; prefers same category; backfills; no-category path; 404 for unpublished source

## 8. Documentation

- [x] 8.1 Write `blogs/docs/backend/blog-system.md` (models, relationships, publish rules, view/popular/related logic, permissions, endpoints)
- [x] 8.2 Write `blogs/docs/frontend/blog-admin.md` (Token auth, category then article workflow, multipart upload, publish, examples)
- [x] 8.3 Write `blogs/docs/frontend/blog-public.md` (list/detail/popular/related, view-count side effect, pagination/limits, empty states, examples)
