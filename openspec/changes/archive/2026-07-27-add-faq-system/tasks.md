## 1. App scaffold and models

- [x] 1.1 Create Django app `faqs` with standard layout (`models`, `admin`, `filters`, `api/`, `services/`, `tests/`, `docs/`)
- [x] 1.2 Implement `FaqType` model with `PublicIdMixin`, `name` (unique), `sort_order`, `is_active`, timestamps
- [x] 1.3 Implement `FaqQuestion` model with `PublicIdMixin`, FK to `FaqType` (`PROTECT`), `question`, `answer`, `is_published` (default false), `sort_order`, timestamps
- [x] 1.4 Add initial migration and register `faqs` in `INSTALLED_APPS`
- [x] 1.5 Register Django Admin for types and questions (list filters, search, inline optional)

## 2. Domain services

- [x] 2.1 Implement `get_public_faq_catalog()` that returns active types with prefetch of published-only questions, ordered by `sort_order`, omitting types with zero published questions
- [x] 2.2 Enforce type-delete guard (reject when questions still exist) in service or view delete path

## 3. Admin FAQ type API

- [x] 3.1 Add admin type serializers (create/update/list/detail) exposing `public_id`, unique `name` validation
- [x] 3.2 Add `FaqTypeViewSet` (list/create/retrieve/patch/delete) with `IsVerifiedAdmin`, `lookup_field=public_id`, pagination, OpenAPI tags
- [x] 3.3 Wire `/faqs/types/` routes

## 4. Admin FAQ question API

- [x] 4.1 Add admin question serializers with `type_public_id` write/read, `is_published`, `sort_order`
- [x] 4.2 Add filters for `type_public_id` and `is_published`, plus search on question/answer
- [x] 4.3 Add `FaqQuestionViewSet` (list/create/retrieve/patch/delete) with `IsVerifiedAdmin`, `lookup_field=public_id`, pagination, OpenAPI tags
- [x] 4.4 Wire `/faqs/questions/` routes and include `faqs.api.urls` in `core/urls.py` under `/faqs/`

## 5. Public FAQ feed API

- [x] 5.1 Add nested public serializers (type + nested published questions; no unpublished leakage)
- [x] 5.2 Add `PublicFaqCatalogViewSet` or equivalent `GET /faqs/public/` with `AllowAny`, no auth classes, using `get_public_faq_catalog()`
- [x] 5.3 Add OpenAPI schema metadata for the public catalog

## 6. Tests

- [x] 6.1 Type API tests: verified admin CRUD success; duplicate name rejected; delete blocked when questions exist; anonymous/non-admin/unverified denied
- [x] 6.2 Question API tests: create under type; default unpublished; publish/unpublish PATCH; filter by type and `is_published`; invalid `type_public_id` rejected; auth denials
- [x] 6.3 Public feed tests: no auth; only published questions nested; unpublished excluded; inactive/empty types omitted; ordering; payload shape without integer `id`

## 7. Documentation

- [x] 7.1 Write `faqs/docs/backend/faq-system.md` (models, publish rules, endpoints, permissions, delete guard)
- [x] 7.2 Write `faqs/docs/frontend/faq-admin.md` (Token auth, create types then questions, publish workflow, examples)
- [x] 7.3 Write `faqs/docs/frontend/faq-public.md` (no-auth nested feed, section/item rendering, empty states, examples)
