## Context

BeFood’s public website needs a regularly updated blog. Verified admins already manage CMS-like content via REST (`faqs`, `notices`, `announcements`) using `IsVerifiedAdmin` and `PublicIdMixin`. There is no blog domain yet.

This change adds a dedicated `blogs` app: admins manage **categories** and **articles** (title, content, cover image, author, publish state); the public site lists published articles, opens detail pages (with view tracking), shows most-popular articles, and suggests related articles.

Stakeholders: verified admins (CRUD + media upload), public website (blog listing/detail/popular/related), backend maintainers (app boundary).

Constraints: follow Django app layout (`api/`, `services/`, `docs/`); reuse `IsVerifiedAdmin`; mount under top-level `/blogs/` like `/faqs/` and `/announcements/`; expose `public_id` only (no sequential `id` to clients); keep business logic in `services/`; do not break existing apps.

## Goals / Non-Goals

**Goals:**

- Own blog categories and articles in app `blogs`.
- Verified-admin REST CRUD for categories and articles (multipart cover image upload).
- Auto-set **author** from the authenticated admin on create; never accept client-supplied author override.
- Auto-set **published_at** when an article transitions to published the first time; leave null while draft.
- Public list + detail of published articles only; atomic **view_count** increment on public detail.
- Public **most popular** endpoint ordered by `view_count`.
- Public **related articles** endpoint based primarily on shared category.
- Backend + frontend docs for admin workflow and public website integration.

**Non-Goals:**

- Comments, likes, bookmarks, or social sharing backend.
- Full-text search engine / Elasticsearch.
- Bilingual fields (`_en` / `_bn`) in v1.
- Schedule windows (`publish_at` / `publish_until`) — use `is_published` + `published_at` only.
- Per-IP / per-session view deduplication (simple `F()` increment is enough for v1).
- Mobile-operator-specific blog routes.
- Hosting a WYSIWYG editor; content is stored as text (plain or HTML string as provided by admin client).

## Decisions

### 1. New app `blogs`

**Why:** Blog is a distinct CMS surface (long-form articles + media + popularity), not a notice or announcement.  
**Alternatives considered:** Reuse `announcements` — rejected (different shape, no view/related semantics). Django Admin only — rejected (product wants frontend-admin REST like FAQs/announcements).

### 2. Data model

```text
BlogCategory (PublicIdMixin)
  name          CharField unique, required
  slug          SlugField unique (auto from name on save if blank)
  sort_order    IntegerField default 0   # lower first in admin filters / optional public filters
  is_active     bool default True
  created_at, updated_at

BlogArticle (PublicIdMixin)
  category      FK → BlogCategory (SET_NULL, null=True, blank=True, related_name='articles')
  author        FK → auth.User (PROTECT, related_name='blog_articles')  # set in service from request.user
  title         CharField required
  slug          SlugField unique (auto from title on create if blank; stable after publish preferred)
  excerpt       CharField/TextField blank  # short card summary; optional
  content       TextField required
  cover_image   ImageField upload_to=blogs/covers/...  required on publish (nullable while draft OK)
  cover_image_title  CharField blank  # alt / image title for accessibility & SEO
  is_published  bool default False
  published_at  DateTimeField null=True, blank=True  # set once on first publish (UTC)
  view_count    PositiveIntegerField default 0
  created_at, updated_at
```

**Indexes:**

- `(is_published, -published_at)` for public list
- `(is_published, -view_count)` for popular
- `(category, is_published)` for related

**Delete rules:**

- Category with articles: **PROTECT** on category delete is safer if we required category; with nullable `SET_NULL`, deleting a category nulls `category` on articles — **Decision: SET_NULL** so admins can retire categories without blocking article history. Soft-hide via `is_active` preferred for public filters.
- Article delete: hard delete (CASCADE media file cleanup via Django signals or `post_delete` optional; document orphan risk).

**Author:** Always `request.user` on create. On update, author remains unchanged (no reassignment in v1). Responses expose `author_public_id` only if User has public id — otherwise expose safe display fields: `author_name` (from `get_full_name()` or username) and omit integer user `id`. **Decision:** expose `author_display_name` string only on public APIs; admin may also show username.

**Cover image:** Required when `is_published=true` (validate on publish). Drafts may omit image. Multipart/form-data for create/update (same pattern as announcements).

**Alternatives:** Tags M2M instead of categories — rejected for v1 simplicity; category covers related matching. Multiple authors — rejected.

### 3. URL and auth layout

```text
# Public (AllowAny, no auth classes)
GET  /blogs/public/                              # paginated published list
GET  /blogs/public/{public_id}/                  # detail; increments view_count
GET  /blogs/public/popular/                      # most popular published
GET  /blogs/public/{public_id}/related/          # related suggestions

# Admin categories
GET|POST          /blogs/categories/             IsVerifiedAdmin
GET|PATCH|DELETE  /blogs/categories/{public_id}/ IsVerifiedAdmin

# Admin articles
GET|POST          /blogs/articles/               IsVerifiedAdmin
GET|PATCH|DELETE  /blogs/articles/{public_id}/   IsVerifiedAdmin
```

Register literal path segments (`public`, `categories`, `articles`, `popular`) before or as non-`public_id` routes so they are never parsed as UUIDs.

**Public list filters (allowlisted):** `category` (`category_public_id`), optional `q` search on title/excerpt. Default sort: `-published_at`, then `id`.  
**Popular query:** `limit` (default 5, max 20). Order: `-view_count`, `-published_at`, `id`.  
**Related query:** `limit` (default 4, max 12). Logic in service (below).

### 4. View count tracking

- On successful public **detail** retrieval of a published article, increment `view_count` with `F('view_count') + 1` (atomic, race-safe).
- Do **not** increment on list, popular, related, or admin endpoints.
- Unpublished / missing articles: `404`; no increment.
- **Decision:** No cookie/IP dedupe in v1 (accept inflated counts from refresh/bots). Document as known trade-off.

### 5. Popular article calculation

- Query published articles only (`is_published=true` and `published_at` not null).
- Order by `view_count` DESC, then `published_at` DESC, then `id`.
- Apply `limit` clamp; paginate or return a simple list (prefer simple list for “Most Popular” widget — **Decision: non-paginated list with limit**).

### 6. Related article recommendation

Service `get_related_articles(article, limit)`:

1. Exclude the current article.
2. Prefer other **published** articles with the **same category** (if category is set), ordered by `-view_count`, `-published_at`.
3. If fewer than `limit`, backfill with other published articles (any category), same ordering, still excluding already selected and self.
4. If category is null, skip step 2 and use global published backfill only.

**Alternatives:** Tag Jaccard / full-text similarity — deferred. Manual “related” M2M — deferred.

### 7. Publish lifecycle

- Create defaults: `is_published=false`, `published_at=null`, `view_count=0`, `author=request.user`.
- When PATCH/create sets `is_published=true` and `published_at` is null → set `published_at=timezone.now()` (UTC).
- Unpublish (`is_published=false`) keeps historical `published_at` (do not clear) so republish retains original publish date — **Decision: keep published_at**.
- Publishing without cover image → `422` validation error.

### 8. Service layer

- `blogs/services/blog_catalog.py` (or split modules):
  - `get_public_article_queryset()` — published filter + select_related category/author
  - `increment_article_views(article)` — F() update
  - `get_popular_articles(limit)`
  - `get_related_articles(article, limit)`
  - `publish_article_fields(...)` helpers for published_at / cover validation as needed
- Views stay thin; serializers validate shape; services own query rules.

### 9. Identifiers and serializers

- All client-facing IDs are `public_id`.
- Nested writes use `category_public_id` (nullable).
- `lookup_field = "public_id"` on ViewSets.
- List card payload (public): `public_id`, `title`, `slug`, `excerpt`, `cover_image` URL, `cover_image_title`, `author_display_name`, `published_at`, `view_count`, optional nested category `{public_id, name}`.
- Detail adds `content`.

### 10. Documentation deliverables

- `blogs/docs/backend/blog-system.md` — models, publish rules, view/popular/related logic, permissions.
- `blogs/docs/frontend/blog-admin.md` — Token auth, category then article workflow, multipart upload, publish.
- `blogs/docs/frontend/blog-public.md` — list/detail/popular/related, no auth, view-count side effect on detail.

## Risks / Trade-offs

- **[Risk] View inflation from refreshes/bots** → Mitigation: document limitation; add IP/session dedupe later if needed.
- **[Risk] Accidental publish without cover** → Mitigation: validate cover required when `is_published=true`.
- **[Risk] Related quality with few articles / no category** → Mitigation: backfill with popular/recent published; empty list OK.
- **[Risk] Large `content` payloads on list** → Mitigation: list serializers omit `content`; detail only.
- **[Trade-off] Category SET_NULL on delete** → Articles lose related signal; prefer deactivating categories.
- **[Trade-off] Single language + no schedule windows** → Matches v1; additive later.

## Migration Plan

1. Add `blogs` app, models, migrations; register in `INSTALLED_APPS` and `core/urls.py`.
2. Deploy migrations; no required data seed (admins create categories/articles).
3. Frontend admin: manage categories → create articles with cover → publish.
4. Frontend website: list `/blogs/public/`, detail `/blogs/public/{id}/`, widgets for popular + related.
5. **Rollback:** remove URL include / disable app; reverse migration only if no critical production dependency.

## Open Questions

- None blocking for implementation. Optional later: require category on publish, view dedupe, tags M2M, scheduled publish.
