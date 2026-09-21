## 1. Schema & models

- [x] 1.1 Add logistics/completion fields on `OrderDelivery` (or 1:1 logistics model): rider attribution FK, zone/location snapshot FKs, `logistics_status`, lifecycle timestamps, completion lat/lng, duration seconds
- [x] 1.2 Create `DeliveryActivityLog` model (delivery, rider, status, timestamp, lat/lng, source, note) with indexes for rider+time and delivery+time
- [x] 1.3 Create `DeliveryManDailySummary` model (rider, date, lunch/dinner/total/completed/failed, average_time) with unique `(rider, date)`
- [x] 1.4 Generate and review migrations (nullable/additive; no destructive changes to meal `status`)

## 2. Mark path & logistics writers (Phase A)

- [x] 2.1 Extend `mark_delivery_and_notify` (and deliveryman mark view/serializer) to accept optional lat/lng; persist attribution, `delivered_at`, activity log, duration when possible
- [x] 2.2 Upsert `DeliveryManDailySummary` on successful deliveryman (and documented admin) completed deliveries; do not count skips as completed KPIs
- [x] 2.3 Ensure legacy mark payload `{status: delivered}` remains backward compatible
- [x] 2.4 Add management command to rebuild daily summaries for a date range from historical `delivered` rows

## 3. Logistics transitions (Phase B hooks)

- [x] 3.1 Implement service for logistics status transitions with timestamp rules and illegal-transition errors
- [x] 3.2 Expose deliveryman (and/or admin) endpoints for `accepted` / `picked_up` / `out_for_delivery` / `failed` as designed; write activity log on each transition
- [x] 3.3 Document Phase A deliver shortcut when intermediates are skipped

## 4. Admin 360 read APIs

- [x] 4.1 Implement `GET /api/v1/web/delivery-men/` list with identity, zone, availability, today/month/lifetime counts; `IsVerifiedAdmin`; pagination
- [x] 4.2 Implement lean `GET /api/v1/web/delivery-men/{public_id}/` overview (no embedded history arrays)
- [x] 4.3 Implement paginated `.../deliveries/` with allowlisted filters (presets/range, meal_period, zone, status); reject unknown filters with `400`
- [x] 4.4 Implement `.../timeline/` for a date (default today in business timezone)
- [x] 4.5 Implement `.../route/` requiring `service_date` + `meal_period`; ordered sequence + coordinates
- [x] 4.6 Implement `.../rankings/` (or collection action) with comparison metrics for allowlisted period
- [x] 4.7 Wire URLs under `/api/v1/web/`; reuse existing deliveryman `public_id` conventions; extend approval list/detail serializers only where additive KPI/zone fields are needed

## 5. Tests

- [x] 5.1 Tests: mark delivered writes attribution, activity log, optional GPS, daily summary; skip does not increment completed KPIs
- [x] 5.2 Tests: admin 360 list/overview auth (`401`/`403`), `404` unknown id, overview excludes history arrays
- [x] 5.3 Tests: deliveries filters, pagination, unknown filter `400`
- [x] 5.4 Tests: timeline ordering; route requires params; rankings period metrics
- [x] 5.5 Tests: logistics illegal transition rejected (Phase B)

## 6. Docs & OpenAPI

- [x] 6.1 Update OpenAPI/schema for new web endpoints and additive mark fields
- [x] 6.2 Write backend docs for Delivery Man 360 analytics + logistics fields
- [x] 6.3 Write frontend docs per `admin-deliveryman-360-frontend-docs` (navigation, section→API map, filters, empty states)
- [x] 6.4 Note open questions resolved during impl (admin mark attribution, failed vs meal status, ranking population, timezone)
