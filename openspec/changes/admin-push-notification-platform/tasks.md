## 1. Database Models & Migration

- [x] 1.1 Add `PushCampaign` model with `PublicIdMixin`, status enums, counters (`total_sent`, `total_failed`, `total_skipped`), audit fields (`ip_address`, `user_agent`, `idempotency_key`), and `target_config` JSONField
- [x] 1.2 Add `PushCampaignRecipient` model with statuses `pending`, `sent`, `failed`, `skipped` and indexes per design
- [x] 1.3 Create and run Django migration for new models
- [x] 1.4 Register models in `notifications/admin.py` (read-only list display)

## 2. Firebase Service Layer

- [x] 2.1 Implement multi-process-safe Firebase init in `fcm_service.py` (`get_app()` check before `initialize_app()`)
- [x] 2.2 Implement `send_to_token()` returning structured `SendResult`
- [x] 2.3 Implement `send_to_tokens()` with 500-token batching
- [x] 2.4 Handle Firebase unregistered/invalid token errors — deactivate via device service
- [x] 2.5 Add `deactivate_device_token_by_value()` to `device_service.py`

## 3. Targeting, Idempotency & Send Services

- [x] 3.1 Create `notification_filter.py` with `resolve_target_users()` and `validate_customer_user_ids()` — CustomerProfile-only; reject staff/rider/admin
- [x] 3.2 Implement filter allowlist reusing admin customer patterns
- [x] 3.3 Implement `resolve_devices_for_users()` — active tokens; mark push-disabled users as `skipped`
- [x] 3.4 Create `notification_sender.py` with `create_campaign()` (returns immediately) and `dispatch_push_campaign(campaign_id)`
- [x] 3.5 Implement idempotency: `Idempotency-Key` header lookup + 5-minute fingerprint dedup → `409 Conflict`
- [x] 3.6 Implement async enqueue via daemon thread after 202 response
- [x] 3.7 Implement dispatch loop: FCM batches, recipient updates, counters, `completed`/`failed` status
- [x] 3.8 Add broadcast confirmation guard (threshold + `confirm_broadcast`)
- [x] 3.9 Create `management/commands/dispatch_push_campaign.py` with `--campaign-id` and `--stuck-only` flags

## 4. Admin API Layer

- [x] 4.1 Create serializers with strict `data` allowlist validation (`screen`, `entity_type`, `entity_id`)
- [x] 4.2 Create send view returning `202 Accepted` with `status=processing` — never block on FCM
- [x] 4.3 Create campaign ViewSet (list, retrieve) with `IsVerifiedAdmin`
- [x] 4.4 Capture `ip_address` and `user_agent` on campaign create
- [x] 4.5 Create `web_urls.py` and mount `/api/v1/web/notifications/` in `core/urls.py`
- [x] 4.6 Add pagination and list filters; include `total_skipped` in list/detail responses

## 5. OpenAPI Documentation

- [x] 5.1 Extend `openapi.py` with async 202 examples, idempotency header, data payload contract, 409 duplicate example
- [x] 5.2 Add `@extend_schema` to all admin notification endpoints
- [x] 5.3 Verify schema generation (`manage.py spectacular --validate`)

## 6. Tests

- [x] 6.1 Permissions: unauthenticated 401, customer 403, verified admin 202
- [x] 6.2 Targeting: single, selected, filtered, all (with confirmation)
- [x] 6.3 Non-customer rejection: staff, rider, admin user IDs → 422
- [x] 6.4 Idempotency: same `Idempotency-Key` returns same campaign; fingerprint dedup → 409
- [x] 6.5 Async: POST returns before FCM completes; poll shows final status
- [x] 6.6 Data payload: valid deep-link accepted; unknown keys rejected
- [x] 6.7 Firebase mock: success, invalid token deactivation, partial failure → `completed` with `total_failed > 0`
- [x] 6.8 Skipped status: push preference opt-out → `skipped`, increments `total_skipped`
- [x] 6.9 Query count ceiling and FCM 500-token batching
- [x] 6.10 Management command dispatches stuck campaigns
- [x] 6.11 Audit fields populated on send

## 7. Documentation

- [x] 7.1 Write backend doc: async flow, idempotency, partial failure, management command, Firebase setup
- [x] 7.2 Write frontend doc: Notification List columns, Send page fields, Detail page, polling UX, preview, Flutter deep-link examples

## 8. Verification

- [x] 8.1 Run full notifications test suite
- [x] 8.2 Smoke test: send to single device → 202 → poll until completed
- [x] 8.3 Confirm device token APIs and in-app Notification scaffold unaffected
