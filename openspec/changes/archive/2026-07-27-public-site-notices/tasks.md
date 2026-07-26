## 1. App scaffold

- [x] 1.1 Create Django app `notices` with standard layout (`models`, `admin`, `api/`, `services/`, `tests/`, `docs/`)
- [x] 1.2 Register `notices` in `INSTALLED_APPS` and mount URLs at `/notices/` from `core/urls.py`

## 2. Models and Django Admin

- [x] 2.1 Add `Notice` model (`PublicIdMixin`, `title_en`/`title_bn`, `body_en`/`body_bn`, `severity` info|warning|critical, `is_published`, optional `publish_at`/`publish_until`, `sort_order`, timestamps)
- [x] 2.2 Enforce validation: at least one of `title_en` or `title_bn` non-empty; validate `publish_until` is after `publish_at` when both set
- [x] 2.3 Create initial migration and register `Notice` in Django Admin with list display, filters (`is_published`, `severity`), search, and computed active/draft/scheduled/expired status

## 3. Active-notice service

- [x] 3.1 Implement `get_active_notices(at=None)` that filters `is_published=True` and schedule window in UTC
- [x] 3.2 Add ordering by `sort_order` ascending then deterministic tie-breaker (`-publish_at` / `-created_at`)

## 4. Public API

- [x] 4.1 Add lean public serializer (`public_id`, bilingual titles/bodies, `severity`, `publish_at`, `publish_until`, `sort_order`)
- [x] 4.2 Add `GET /notices/active/` with `AllowAny`, pagination (default + max page size), returning only active notices
- [x] 4.3 Add OpenAPI schema entries for the public active feed

## 5. Tests

- [x] 5.1 Model/admin validation tests: empty dual titles rejected; invalid severity rejected; schedule window validation
- [x] 5.2 Service tests: draft hidden; future `publish_at` hidden; past `publish_until` hidden; open-ended published visible; sort order respected
- [x] 5.3 API tests: anonymous `200` on active feed; drafts/expired omitted; bilingual fields present; pagination bounds

## 6. Documentation

- [x] 6.1 Add `notices/docs/backend/overview.md` (model fields, active rule, Admin publish workflow, expiry behavior)
- [x] 6.2 Add `notices/docs/frontend/site-notices.md` (public endpoint, no auth, JSON examples, locale fallback, severity UI states, empty state)
