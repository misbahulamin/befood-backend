## Why

BeFood’s public website has no way for admins to broadcast time-bound announcements (service outages, holiday hours, promotions, policy updates) to all visitors. Operators need a bilingual (English + Bangla) notice that can be drafted privately, published on demand, and automatically stop showing after an expiry time — without requiring visitor login.

## What Changes

- Create a new Django app `notices` that owns site-wide public notices.
- Support bilingual notice copy: English and Bangla title and body fields.
- Allow admins to draft notices with `is_published=false`, then flip to published when ready.
- Support an optional `publish_until` datetime; after that instant a notice is treated as inactive even if `is_published` remains true (admin can still unpublish manually).
- Optionally support `publish_at` so a notice can be scheduled to become visible in the future.
- Manage notices primarily via Django Admin (create, edit, publish/unpublish, set expiry).
- Expose a **public, unauthenticated** read API for the website frontend that returns only currently active notices.
- Ship clear backend and frontend documentation for the public contract and admin workflow.

## Capabilities

### New Capabilities

- `site-notice-management`: Admin-managed bilingual notice records with publish flag, optional schedule window (`publish_at` / `publish_until`), severity/type for UI styling, and soft lifecycle (draft → published → expired/unpublished).
- `public-notice-feed`: Unauthenticated public API that returns only notices that are published and within their active time window, ordered for website display.

### Modified Capabilities

- (none)

## Impact

- **New app:** `notices` registered in `INSTALLED_APPS`; URLs mounted from `core/urls.py` (public feed under a stable public path, e.g. `/notices/`).
- **Models / migrations:** `Notice` with `PublicIdMixin`, bilingual text fields, publish flags, schedule timestamps.
- **Django Admin:** full CRUD and publish controls for staff/admins.
- **APIs:** public `AllowAny` list (and optional detail) for active notices; no auth required for visitors.
- **Docs:** `notices/docs/backend/` and `notices/docs/frontend/` describing admin workflow and public API contract.
- **Out of scope:** per-user notification inbox, push/email delivery, rich HTML CMS, A/B targeting, multi-tenant notices, authenticated admin REST CRUD for notices in v1 (Django Admin is the management surface).
