## Why

Customers need a clear, trustworthy answer to “when does BeFood deliver?” for each meal window (Lunch, Dinner, and future custom types). Today delivery *windows* are not a managed catalog—only operational lunch/dinner cutoffs and reveal times exist as hardcoded fields—and the customer package-detail page hardcodes Bangla Lunch/Dinner windows in static content, so admins cannot add Breakfast/Sehri/Iftar or change windows without code changes.

## What Changes

- Add a **dynamic Delivery Schedule catalog** (admin-managed delivery types with start/end local times, active flag, and sort order)—not a hardcoded Lunch/Dinner enum.
- Add **admin CRUD APIs** (verified admin) and a **public read API** that returns only active schedules ordered by `sort_order`.
- Add **admin frontend** management UI (list/create/edit/activate/deactivate/delete) under System (alongside FAQs/Settings).
- Replace **hardcoded package-detail delivery windows** (`detailStaticContent.ts` Lunch/Dinner times) with public API data; optionally refresh homepage TrustStrip/ServiceHub from the same API.
- Document that this feature is **informational display only** in v1: it does **not** replace or redefine operational `meal_period` (`lunch`/`dinner`) used by orders, kitchen, meal-off, menu reveal, or delivery boards.
- Seed optional default Lunch/Dinner rows via migration/data migration so the public API is useful immediately (admin can change them).

## Capabilities

### New Capabilities

- `delivery-schedule-admin`: Admin CRUD for delivery schedule records (name, start/end `TimeField`, `is_active`, `sort_order`, public UUID identity), validation, hard delete, OpenAPI.
- `delivery-schedule-public`: Unauthenticated public list of active schedules sorted by `sort_order` for customer/marketing UIs.
- `delivery-schedule-frontend-docs`: Frontend integration contracts for admin CRUD and public display (endpoints, payloads, timezone/time formatting notes).

### Modified Capabilities

- (none — no existing main `openspec/specs/` capability defines a dynamic delivery-window catalog; operational `customer-meal-off` / `monthly-menu-schedule` lunch/dinner fields remain unchanged)

## Impact

- **Backend:** New Django app `delivery_schedules` (models, services, API, tests, docs); register in `INSTALLED_APPS` and `core/urls.py`.
- **Admin web:** New routes, sidebar entry, API client, hooks, list/modal form pages in `befood-frontend`.
- **Customer web:** Package detail policies driven by public API (primary); optional homepage TrustStrip/ServiceHub dynamic copy.
- **Non-goals / no change:** `MealCategory.MealPeriod`, `OrderDelivery.MealPeriod`, `MealOffSettings`, `MenuRevealSettings`, kitchen/board period filters—remain lunch/dinner operational enums.
- **Timezone:** Wall-clock `TimeField` values interpreted in `Asia/Dhaka` (same convention as meal-off/reveal times); `TIME_ZONE = Asia/Dhaka`, `USE_TZ = True`.
