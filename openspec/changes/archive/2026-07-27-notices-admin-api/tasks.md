## 1. Admin serializer and filters

- [x] 1.1 Add `NoticeAdminSerializer` with bilingual fields, publish/schedule fields, `sort_order`, timestamps, and read-only `lifecycle_status`
- [x] 1.2 Wire create/update validation through model `full_clean()` (shared title + schedule rules)
- [x] 1.3 Add `NoticeFilter` for `is_published`, `severity`, and search across titles/bodies

## 2. Admin ViewSet and routes

- [x] 2.1 Add `NoticeViewSet` (list/create/retrieve/patch/delete) with `IsVerifiedAdmin`, `lookup_field=public_id`, pagination, ordering
- [x] 2.2 Register routes so `/notices/` is admin CRUD and `/notices/active/` remains the public feed (register `active` first; add URL resolution test)
- [x] 2.3 Add OpenAPI schema tags/summaries for admin notice operations

## 3. Tests

- [x] 3.1 API tests: verified admin create/list/retrieve/patch/delete; anonymous and non-admin denied
- [x] 3.2 API tests: validation errors (empty dual titles, invalid schedule); filters (`is_published`, `severity`); `lifecycle_status` values
- [x] 3.3 Regression: public `GET /notices/active/` still `AllowAny` and omits drafts

## 4. Documentation

- [x] 4.1 Update backend overview with admin REST surface vs Django Admin vs public feed
- [x] 4.2 Add/update frontend admin docs (Token auth, endpoint grid, examples, publish → public feed workflow)
