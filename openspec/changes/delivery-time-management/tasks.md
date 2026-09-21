## 1. Backend app scaffold

- [x] 1.1 Create Django app `delivery_schedules` with standard layout (`models.py`, `admin.py`, `filters.py`, `api/`, `services/`, `tests/`, `docs/`)
- [x] 1.2 Register `delivery_schedules` in `core/settings/base.py` `INSTALLED_APPS`
- [x] 1.3 Add `DeliverySchedule` model (`PublicIdMixin`, `name` unique, `start_time`/`end_time` `TimeField`, `is_active`, `sort_order`, timestamps) with `clean()` validation (`start_time < end_time`, stripped name)
- [x] 1.4 Create schema migration and idempotent data migration seeding Lunch `12:30–14:30` and Dinner `19:00–21:00` when table empty (match current `detailStaticContent.ts` windows)
- [x] 1.5 Register model in Django admin for emergency ops visibility

## 2. Backend services and admin API

- [x] 2.1 Implement service helpers for public queryset (active + ordering) and any create/update/delete rules
- [x] 2.2 Implement admin serializers + filters (`is_active`, search on `name`, ordering whitelist)
- [x] 2.3 Implement admin ViewSet (list/retrieve/create/partial_update/destroy) with `IsVerifiedAdmin`, `lookup_field=public_id`, pagination
- [x] 2.4 Mount router under `/delivery-schedules/` in `core/urls.py` (register `public` prefix before detail routes)
- [x] 2.5 Add drf-spectacular `@extend_schema` / `@extend_schema_view` tags and descriptions

## 3. Backend public API

- [x] 3.1 Implement public list ViewSet/mixin (`AllowAny`, no auth classes, GET-only, no pagination or safe small catalog)
- [x] 3.2 Ensure inactive rows are excluded and ordering is `sort_order`, `name`, `id`
- [x] 3.3 Expose public serializer fields: `public_id`, `name`, `start_time`, `end_time`, `sort_order`

## 4. Backend tests and docs

- [x] 4.1 Add API tests: admin CRUD happy path, auth denial, validation (blank name, duplicate name, overnight/equal times), public list filtering/ordering
- [x] 4.2 Write `delivery_schedules/docs/backend/delivery-time-management.md` (models, permissions, workflows, examples)
- [x] 4.3 Write `delivery_schedules/docs/frontend/delivery-time-management.md` (admin + public contracts, snake_case examples, timezone notes)

## 5. Admin frontend (befood-frontend)

- [x] 5.1 Add `adminRoutes.deliveryTimes` in `src/config/routes.ts` and route entry in `src/app/router.tsx`
- [x] 5.2 Add “Delivery Times” nav item under System (or Operations) in `src/features/admin/components/AdminSidebar.tsx` (+ breadcrumb title in `AdminLayout.tsx` if required)
- [x] 5.3 Add types, API client (`adminApi`), TanStack Query hooks, and zod schema for delivery schedules
- [x] 5.4 Build `AdminDeliveryTimesPage` list cloning Ingredients (or FAQ-type) modal CRUD patterns
- [x] 5.5 Build create/edit modal form with `type="time"` inputs, active toggle, sort order; delete confirmation via `AdminModal`; toast via `sonner`
- [x] 5.6 Wire activate/deactivate (PATCH `is_active`) and verify loading/error states

## 6. Customer frontend display

- [x] 6.1 Add public API client (`createPublicApiClient`) + hook for `GET /delivery-schedules/public/`
- [x] 6.2 Replace hardcoded Lunch/Dinner windows in `src/features/monthly-package/data/detailStaticContent.ts` (`detailPolicies`) with API-driven rows in package detail UI
- [x] 6.3 Optionally refresh `TrustStrip` / `ServiceHub` (and/or add homepage section) from the same public list
- [x] 6.4 Format times for `bn` display from API values; ensure no hardcoded schedule names or windows remain in source
- [x] 6.5 Confirm display order matches `sort_order` from API

## 7. Verification

- [x] 7.1 Run backend test suite for `delivery_schedules`
- [x] 7.2 Manual E2E: admin creates Breakfast 08:00–10:00 → activate → public API returns it → package detail (and any home surface) shows it without redeploying type lists
- [x] 7.3 Confirm operational Settings meal-off/reveal Lunch/Dinner fields remain unchanged and unrelated
