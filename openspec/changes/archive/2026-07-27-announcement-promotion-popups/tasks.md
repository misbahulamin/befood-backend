## 1. App scaffold and model

- [x] 1.1 Create Django app `announcements` with standard layout (`models`, `admin`, `filters`, `api/`, `services/`, `tests/`, `docs/`)
- [x] 1.2 Implement `Announcement` model with `PublicIdMixin`, type/severity enums, optional image + CTA fields, publish schedule, priority, timestamps, and model `clean()` validation
- [x] 1.3 Add migration `0001_initial` and register app in `INSTALLED_APPS`
- [x] 1.4 Register Django Admin for announcements (list filters, searchable fields, optional lifecycle display)

## 2. Domain services

- [x] 2.1 Implement `get_active_announcements(at=None)` with inclusive `publish_until` rule and priority-desc / newest ordering
- [x] 2.2 Implement `compute_lifecycle_status` (`draft` | `scheduled` | `active` | `expired`)

## 3. Admin API

- [x] 3.1 Add admin serializers (create/update + `lifecycle_status`) with model validation mapping and multipart image support
- [x] 3.2 Add `AnnouncementFilter` (`is_published`, `type`, `severity`) and search/ordering config
- [x] 3.3 Add `AnnouncementViewSet` (list/create/retrieve/patch/delete) with `IsVerifiedAdmin`, `lookup_field=public_id`, pagination, OpenAPI tags
- [x] 3.4 Wire router under `/announcements/` (register `active` before collection) and include in `core/urls.py`

## 4. Public active feed API

- [x] 4.1 Add lean `PublicAnnouncementSerializer` (popup fields only)
- [x] 4.2 Add `ActiveAnnouncementViewSet` (`AllowAny`, no auth classes, paginated list using `get_active_announcements`)
- [x] 4.3 Add OpenAPI schema metadata for the public feed

## 5. Tests

- [x] 5.1 Test model validation (title required, schedule window, CTA pairing, enums)
- [x] 5.2 Test active queryset rules (draft/scheduled/expired boundaries, inclusive `publish_until`, priority ordering)
- [x] 5.3 Test admin CRUD auth (401/403), create/patch/delete by `public_id`, publish/unpublish, filters, multipart image upload
- [x] 5.4 Test public feed (no auth, empty set, excludes non-active, payload shape, pagination)

## 6. Documentation

- [x] 6.1 Write `announcements/docs/backend/overview.md` (model, active rule, endpoints, permissions)
- [x] 6.2 Write `announcements/docs/frontend/announcements-admin.md` (Token auth, CRUD examples, multipart image, filters)
- [x] 6.3 Write `announcements/docs/frontend/announcements-public.md` (fetch on load, popup types, priority, localStorage dismiss flow, examples)
