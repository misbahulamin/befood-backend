## Context

BeFood’s public website currently has no backend-backed channel for site-wide announcements. Admins need to draft bilingual (English / Bangla) notices in Django Admin, control visibility with a publish flag, and auto-hide them after an expiry time. Website visitors must read active notices without authentication.

Stakeholders: Django Admin staff (create/publish), website frontend (render banner/modal), backend maintainers (app boundary + public contract).

Constraints: follow existing Django app layout (`api/`, `services/`, `docs/`), use `PublicIdMixin` for API identity, keep public payloads lean, and document the frontend contract clearly.

## Goals / Non-Goals

**Goals:**

- Add Django app `notices` as the sole owner of public site notices.
- Model bilingual title/body, publish flag, and optional schedule window (`publish_at`, `publish_until`).
- Define a clear “active” rule used by the public API (and reusable from a service).
- Manage notices via Django Admin in v1.
- Expose an unauthenticated public list API of currently active notices.
- Ship backend + frontend documentation with request/response examples.

**Non-Goals:**

- Authenticated admin REST CRUD for notices (Django Admin only in v1).
- Push notifications, email, SMS, or in-app user inbox.
- Rich HTML / WYSIWYG CMS, attachments, or media galleries.
- Per-user or segment targeting (geo, plan, logged-in only).
- Multi-branch / multi-tenant notice scoping.
- Automatic cron job that flips `is_published` to false on expiry (time-window filtering is enough).

## Decisions

### 1. App name: `notices`

Python package `notices`; URL prefix `/notices/`; product label **Site Notices**.  
**Why:** Short, conventional, matches domain language.  
**Alternatives:** `announcements` (longer); `cms` (too broad).

### 2. Single `Notice` model with bilingual fields

```text
Notice
  public_id
  title_en, title_bn
  body_en, body_bn          # plain text; frontend chooses locale
  severity                  # info | warning | critical (UI hint)
  is_published              # admin publish toggle
  publish_at                # optional; null = immediately eligible when published
  publish_until             # optional; null = no automatic end
  sort_order                # lower first among active notices
  created_at, updated_at
```

At least one locale’s title MUST be non-empty on save (admin validation). Prefer both locales filled for production use; docs recommend bilingual content.  
**Why:** Explicit EN/BN columns match BeFood’s bilingual product surface without introducing a general i18n framework.  
**Alternatives:** JSON `translations` blob — flexible but harder to admin/validate; rejected for v1.

### 3. Active notice rule (computed, not a stored status)

A notice is **active** when all of the following hold at evaluation time (UTC):

1. `is_published` is true
2. `publish_at` is null OR `publish_at <= now`
3. `publish_until` is null OR `publish_until > now`

Expired notices remain in the DB with `is_published` unchanged; the public feed simply omits them. Admins can still unpublish manually.  
**Why:** Avoids background jobs and racey “auto-unpublish” writes; expiry is deterministic from timestamps.  
**Alternatives:** Cron that sets `is_published=false` — extra moving parts; rejected for v1.

### 4. Management surface: Django Admin first

Staff create/edit/publish notices in Django Admin with list filters (`is_published`, severity) and a clear display of “currently active” (computed admin column or filter).  
**Why:** User requirement centers on admin panel publishing; REST admin CRUD can be added later if needed.  
**Alternatives:** Full JWT admin API like `inventory` — more work without a requested management UI beyond Admin.

### 5. Public API: lean, unauthenticated list

```text
GET /notices/active/     AllowAny
```

Returns currently active notices only, ordered by `sort_order` ascending, then `-publish_at` / `-created_at` as tie-breakers.  
Response fields: `public_id`, bilingual titles/bodies, `severity`, `publish_at`, `publish_until`, `sort_order`.  
No draft/expired/unpublished rows. Optional `GET /notices/active/{public_id}/` for detail if useful; list is the primary contract.  
Pagination: small default page size (e.g. 20) with a hard max — active sets are expected to be tiny, but still paginate per project rules.  
**Why:** Website needs a single fetch on load; `AllowAny` matches “no auth for visitors.”  
**Alternatives:** GraphQL / WebSocket push — overkill for v1.

### 6. Service layer owns “active” queryset

`notices/services/catalog.py` (or `active.py`) exposes `get_active_notices(at=None)` used by the public view and optionally by Admin display helpers. Views stay thin.  
**Why:** Matches project convention; keeps the active rule in one place for tests.

### 7. Documentation as a first-class deliverable

- `notices/docs/backend/overview.md` — model fields, active rule, Admin workflow.
- `notices/docs/frontend/site-notices.md` — public endpoint, auth (none), JSON examples, locale selection guidance, UI states (empty / one / many / severity).

## Risks / Trade-offs

- **[Risk] Admins leave `is_published=true` forever after expiry** → Mitigation: Admin list shows “Active / Expired / Draft” computed status; docs explain expiry does not flip the flag.
- **[Risk] Empty second locale on frontend** → Mitigation: require at least one title; frontend falls back to the other locale; docs recommend filling both.
- **[Risk] Public endpoint abuse / scraping** → Mitigation: lean payload, pagination max, existing project rate limits if any; no sensitive fields exposed.
- **[Trade-off] No admin REST API in v1** → Faster ship; management UX is Django Admin only until a later change.
- **[Trade-off] Soft expiry via filter, not auto-unpublish** → Simpler ops; reporting “was published but expired” stays accurate.

## Migration Plan

1. Add `notices` app + initial migration; register in `INSTALLED_APPS` and Admin.
2. Mount public URLs in `core/urls.py`.
3. Deploy; create first notice in Admin as draft, then publish with `publish_until`.
4. Frontend integrates `GET /notices/active/` (no auth).
5. Rollback: remove URL include and/or disable app; data can remain.

## Open Questions

- None blocking for v1. (Future: admin REST CRUD, dismissible client-side “seen” keys, link CTA URL field — defer unless requested.)
