## Why

BeFood’s public website needs promotional banners and offer popups (with optional images and CTAs) that verified admins can create, schedule, and publish from the frontend admin panel—without Django Admin. Existing site `notices` cover bilingual operational alerts only; they lack announcement types, banner images, CTA buttons, and popup-oriented priority semantics. Marketing and ops need a dedicated announcement/promotion surface so visitors see the right popup at the right time.

## What Changes

- Add a new Django app `announcements` with an `Announcement` model (title, description, type, severity, optional image, optional CTA text/URL, publish flags and schedule window, priority, timestamps, `public_id`).
- Add verified-admin REST CRUD (create, list, retrieve, patch, delete) including publish/unpublish, schedule fields, and banner image upload via multipart.
- Add a public unauthenticated active feed that returns only currently visible announcements, sorted by priority descending then newest first.
- Keep existing `notices`, meals, orders, and auth systems unchanged; do not merge into or replace the notices feed.
- Add OpenAPI coverage plus backend and frontend markdown docs (admin + public integration, including localStorage dismiss guidance for the website).

## Capabilities

### New Capabilities

- `announcement-catalog`: Persistent announcement/promotion records with typed categories, severity, optional banner image and CTA, publish schedule, and priority ordering.
- `announcement-admin-api`: Token-authenticated verified-admin CRUD for announcements (`public_id` lookup), including image upload and publish controls.
- `public-announcement-feed`: Unauthenticated paginated feed of currently active announcements for the public website popup/modal UI.

### Modified Capabilities

- (none)

## Impact

- **New app:** `announcements` (models, admin, services, api, filters, tests, docs).
- **Settings / URLs:** register app; mount under `/announcements/` (same top-level style as `/notices/`).
- **Auth:** `IsVerifiedAdmin` for admin CRUD; `AllowAny` + no auth classes for the public active feed.
- **Media:** optional `ImageField` under media storage (same pattern as meal thumbnails).
- **Docs:** `announcements/docs/backend/` and `announcements/docs/frontend/`.
- **Out of scope:** implementing the React popup UI in this backend repo; push/email; A/B targeting; merging with `notices`.
