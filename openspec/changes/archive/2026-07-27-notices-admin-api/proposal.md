## Why

Site notices already exist with Django Admin and a public active feed, but verified admins cannot manage them from the web management UI the way they manage meals and ingredients. Operators need the same token-authenticated admin REST CRUD pattern so the frontend admin panel can create, publish, edit, and delete notices without opening Django Admin.

## What Changes

- Add verified-admin REST CRUD for `Notice` resources under `/notices/` (alongside the existing public `GET /notices/active/`).
- Mirror the meals/ingredients admin pattern: `IsVerifiedAdmin`, `public_id` lookup, list filters, pagination, OpenAPI tags.
- Allow create / list / retrieve / partial update / delete of bilingual notices, including `is_published`, schedule window, severity, and sort order.
- Enforce the same model validation rules via the API (at least one title locale; `publish_until` after `publish_at`).
- Update frontend and backend documentation for the admin contract (auth, endpoints, examples).
- Keep the public active feed unchanged and unauthenticated.

## Capabilities

### New Capabilities

- `notices-admin-api`: Token-authenticated verified-admin CRUD API for site notices (list/filter, create, retrieve, patch, delete) using `public_id`, with OpenAPI and admin frontend docs.

### Modified Capabilities

- (none) — `public-notice-feed` behavior is unchanged; Django Admin management remains available as an alternate surface.

## Impact

- **App:** extend `notices` (`api/views.py`, serializers, filters, urls, tests, docs).
- **Auth:** `IsVerifiedAdmin` (same as ingredients / meal cycle admin).
- **URLs:** e.g. `/notices/` collection for admin CRUD; existing `/notices/active/` stays public-only.
- **Docs:** update `notices/docs/frontend/` and `notices/docs/backend/` with admin API workflow.
- **Out of scope:** changing the public feed contract; push/email; rich HTML CMS; removing Django Admin.
