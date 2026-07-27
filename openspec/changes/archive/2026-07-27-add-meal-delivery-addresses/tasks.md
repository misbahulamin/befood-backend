## 1. Data model & migrations

- [x] 1.1 Add `CustomerDeliveryPlace` model in `user_management` (`PublicIdMixin`, label, address fields, `is_active`, FK to `CustomerProfile`)
- [x] 1.2 Add `MealDeliveryPreference` (1:1 with profile; nullable `lunch_place` / `dinner_place` FKs with ownership validation in services)
- [x] 1.3 Add `MealDeliveryDayOverride` with unique `(customer_profile, meal_period, weekday)` → place FK
- [x] 1.4 Add `OrderDelivery` snapshot fields + nullable `delivery_place` FK (`SET_NULL`) in `orders`
- [x] 1.5 Generate and review migrations for both apps
- [x] 1.6 Data migration: present `is_default_delivery` → delivery place + lunch/dinner preferences for existing customers

## 2. Domain services

- [x] 2.1 Implement delivery-place CRUD service (soft cap, ownership, deactivate/delete rules when referenced by preferences)
- [x] 2.2 Implement preference + day-override write services with ownership checks
- [x] 2.3 Implement `resolve_delivery_address(customer, service_date, meal_period)` with override → default → fallback precedence (`Asia/Dhaka` weekday)
- [x] 2.4 Implement apply-snapshot helper for `OrderDelivery` create/update
- [x] 2.5 Implement `resync_future_scheduled_deliveries(customer)` for preference/place changes (skip delivered/skipped/missed)

## 3. Customer APIs

- [x] 3.1 Serializers for delivery places, preferences, day overrides, and optional date-range preview
- [x] 3.2 ViewSet/API for delivery places list/create/retrieve/patch/delete under `user_management`
- [x] 3.3 Preferences GET/PUT endpoint (`lunch_place_id`, `dinner_place_id` as public UUIDs)
- [x] 3.4 Day-overrides GET/PUT (replace-set or documented upsert) endpoint
- [x] 3.5 Optional preview endpoint returning resolved place per date + meal period
- [x] 3.6 Wire URLs; enforce auth + customer ownership (`404` for foreign ids)
- [x] 3.7 Update profile-completion rule to accept migrated preferences / delivery places (keep present-default fallback during transition)

## 4. Order delivery integration

- [x] 4.1 Hook resolution + snapshot write into `OrderDelivery` creation path(s)
- [x] 4.2 Expose snapshot fields on customer/ops delivery serializers
- [x] 4.3 Optional management command to backfill snapshots for future `scheduled` deliveries missing addresses

## 5. Admin

- [x] 5.1 Register delivery places, preferences, and day overrides in Django admin
- [x] 5.2 Show readonly address snapshot fields on `OrderDelivery` admin

## 6. Tests

- [x] 6.1 Place CRUD, ownership, validation, soft-cap, and delete-when-in-use tests
- [x] 6.2 Preference + weekday override validation and ownership tests
- [x] 6.3 Resolution precedence tests (override vs default vs weekend fallback)
- [x] 6.4 OrderDelivery snapshot-at-create and immutability for delivered rows tests
- [x] 6.5 Future scheduled resync on preference change tests
- [x] 6.6 Migration/backfill path test for present default → preferences

## 7. Docs

- [x] 7.1 Backend docs: models, resolution rules, API contracts, migration notes
- [x] 7.2 Frontend docs: simple UX (My places → Usual lunch/dinner → Optional weekday exceptions + preview)
- [x] 7.3 Note legacy `is_default_delivery` / present-address behavior during transition
