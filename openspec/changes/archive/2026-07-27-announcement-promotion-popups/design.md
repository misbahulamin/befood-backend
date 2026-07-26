## Context

BeFood already ships bilingual **site notices** (`/notices/`) for operational alerts. Marketing and ops also need **promotional popups**—typed announcements with optional banner images and CTA buttons—managed from the verified-admin web panel and shown automatically on the public website.

This change adds a separate `announcements` app so popup/promotion concerns do not overload the notices contract. Patterns mirror `notices` (PublicIdMixin, `IsVerifiedAdmin` CRUD, `get_active_*` service, public `.../active/` list) and meal image upload (multipart `ImageField`).

Stakeholders: verified admins (CRUD + schedule), public website (fetch + popup UX), backend maintainers (app boundary).

Constraints: follow Django app layout (`api/`, `services/`, `docs/`); do not break notices, meals, orders, or auth; use project URL style (top-level `/announcements/`, not a new `/api/` mount unless the project later unifies prefixes).

## Goals / Non-Goals

**Goals:**

- Own announcement/promotion records in app `announcements`.
- Support type, severity, optional image, optional CTA (`button_text` / `button_url`), publish flag, schedule window, and priority.
- Verified-admin REST CRUD with image upload and publish/unpublish via PATCH.
- Public unauthenticated active feed with clear visibility rules and priority-desc ordering.
- Backend + frontend docs: admin workflow, public integration, dismiss/localStorage guidance for the website team.

**Non-Goals:**

- Implementing React popup components in this backend repository.
- Merging with or changing `notices` APIs.
- Push/email/SMS, per-user targeting, A/B tests, or analytics events.
- Rich HTML CMS / WYSIWYG body.
- Background job that flips `is_published` on expiry (time-window filtering is enough).
- Session dismiss storage on the server (client localStorage only).

## Decisions

### 1. New app `announcements` (do not extend `notices`)

**Why:** Notices are bilingual operational banners without image/CTA; announcements are promotion/popup-oriented with different enums and sort semantics. Separate apps keep public contracts stable.  
**Alternatives considered:** Extend `Notice` with nullable image/CTA — rejected (breaks lean bilingual feed and mixes product concerns).

### 2. Model field set and enums

```text
Announcement (PublicIdMixin)
  title                 CharField
  description           TextField (blank allowed)
  type                  notice | offer | new_package | maintenance | announcement
  severity              info | warning | success | error
  image                 ImageField optional (upload_to announcements/banners/)
  button_text           CharField blank optional
  button_url            URLField blank optional
  is_published          bool
  publish_at            DateTimeField null/blank
  publish_until         DateTimeField null/blank
  priority              IntegerField default 0  # higher shows first
  created_at, updated_at
```

API enum values use **lowercase** `TextChoices` to match meals/notices (map product labels NOTICE → `notice`, NEW_PACKAGE → `new_package`, etc.).  
**CTA validation:** if `button_text` is non-empty, `button_url` MUST be a valid URL; if both empty, text-only / image-only popup is allowed.  
**Title:** required non-blank.  
**Schedule:** if both set, `publish_until` MUST be after `publish_at`.

### 3. Active visibility rule (service-owned)

An announcement is **active** at evaluation time `now` (UTC) when:

1. `is_published` is true  
2. `publish_at` is null OR `publish_at <= now`  
3. `publish_until` is null OR `publish_until >= now`

Sort for public feed:

1. `priority` descending  
2. `-created_at` (newest first)  
3. `-id` tie-breaker  

Expose `get_active_announcements(at=None)` in `announcements/services/`. Admin responses may include computed `lifecycle_status` (`draft` | `scheduled` | `active` | `expired`) like notices.

**Note vs notices:** notices use exclusive end (`publish_until > now`); announcements follow the product rule inclusive end (`>=`). Document the difference so frontend teams do not assume identical expiry semantics.

### 4. URL and auth layout

```text
GET               /announcements/active/              AllowAny (no auth classes)
GET|POST          /announcements/                     IsVerifiedAdmin
GET|PATCH|DELETE  /announcements/{public_id}/         IsVerifiedAdmin
```

Register public `active` route before the collection so `"active"` is not parsed as a `public_id`.  
**Path note:** Product copy may say `/api/announcements/active/`; this repo mounts feature apps at the site root (`/notices/`, `/meals/`). Document the real path as `/announcements/active/` in frontend docs. Do not introduce a parallel `/api/announcements/` unless a project-wide API prefix migration is requested.

Admin list: filter by `is_published`, `type`, `severity`; search title/description; paginate (default ~50, max ~200). Public list: paginate (default 20, max 50).

### 5. Image upload

Admin create/update accept `multipart/form-data` when an image is present (same pattern as meal thumbnails). JSON create without image remains valid. Clearing image: allow PATCH with explicit null/empty if serializer supports it; otherwise document “replace only” for v1 and prefer replace-or-omit.

### 6. Frontend UX contract (docs only in this repo)

Document that the website SHOULD:

- Fetch active list on load  
- Show highest-priority first (API order)  
- Support image + text-only popups and multiple actives  
- Persist dismissed `public_id`s in `localStorage` for the session (or longer, as product chooses)  
- Not send auth on the public feed  

Dismiss logic is **client-side only**; the API always returns all currently active rows.

### 7. Documentation deliverables

- `announcements/docs/backend/overview.md` — model, active rule, admin auth  
- `announcements/docs/frontend/announcements-public.md` — public feed + popup integration  
- `announcements/docs/frontend/announcements-admin.md` — admin CRUD + multipart  

## Risks / Trade-offs

- **[Risk] Confusion with `/notices/active/`** → Mitigation: docs state when to use notices vs announcements; keep separate OpenAPI tags.  
- **[Risk] Inclusive vs exclusive `publish_until` vs notices** → Mitigation: document clearly; cover with unit tests at the boundary timestamp.  
- **[Risk] Large banner images** → Mitigation: reuse project media validation patterns where present; document recommended dimensions in frontend docs.  
- **[Risk] Multiple simultaneous popups overwhelm UX** → Mitigation: API returns ordered list; frontend docs recommend showing top priority first and stacking or “next” for the rest.  
- **[Trade-off] Single-language title/description** → Matches stated product fields; bilingual can be a later change without touching notices.

## Migration Plan

1. Add app + migration `0001_initial`.  
2. Register in `INSTALLED_APPS` and `core/urls.py`.  
3. Deploy; no data backfill required.  
4. Rollback: remove URL include and app (drop table only if intentionally rolling back schema).

## Open Questions

- None blocking: path prefix (`/announcements/` vs `/api/...`) resolved to match existing repo mounts; bilingual content deferred.
