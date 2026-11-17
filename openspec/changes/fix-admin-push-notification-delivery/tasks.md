# Tasks

## 1. Diagnose and lock regression fixtures

- [x] 1.1 Reproduce the admin campaign path in tests/fixtures covering inbox-created + FCM-exception leaving status terminal (not `processing`) and verify the new failing-before-fix case is expressed as a test that currently fails or is newly asserted
- [x] 1.2 Confirm production migration `user_management.0025_device_token_length_512` is applied (or document deploy step) and verify model/API max token length remains 512 end-to-end

## 2. Harden FCM send for mixed platforms

- [x] 2.1 Update `fcm_service.send_to_tokens` (or helper) to platform-split native vs web batches with appropriate Android vs Webpush configs and verify unit/integration tests cover mixed android+web success/partial-failure
- [x] 2.2 Narrow `_classify_error` invalid-token detection so non-unregistered errors do not deactivate tokens and verify a non-invalid failure keeps `DeviceToken.is_active=True`
- [x] 2.3 Ensure unexpected FCM/SDK exceptions propagate a controlled failure result (or raise a typed error) that dispatch can finalize safely and verify the exception path is covered by tests

## 3. Harden campaign dispatch and inbox semantics

- [x] 3.1 Wrap `dispatch_push_campaign` so any unexpected error after start finalizes campaign + pending recipients and verify a mocked raise leaves status `failed`/`completed` never stuck `processing`
- [x] 3.2 Keep inbox creation for non-skipped targets independent of FCM success, add re-dispatch inbox dedupe by user+campaign, and verify inbox tests for no-device and multi-device cases
- [x] 3.3 Confirm `total_sent` increments only on FCM success and verify admin list/detail serializers still expose accurate counters after dispatch

## 4. Recovery, docs, and verification

- [x] 4.1 Verify `manage.py dispatch_push_campaign --stuck-only` resumes pending recipients after the hardened dispatcher and add/adjust the management-command test if needed
- [x] 4.2 Update `notifications/docs/backend/admin-push-notifications.md` (and frontend admin note if needed) explaining inbox vs FCM `sent`, platform-split send, and stuck recovery; verify docs match implemented behavior
- [x] 4.3 Run `notifications.tests.test_admin_push_notifications`, `test_notification_inbox`, and `test_device_token` and verify they pass
- [x] 4.4 Manual verification checklist after deploy: single-user Android push arrives on device; same campaign appears in `app.befood.com.bd` inbox; admin poll reaches terminal status with correct `sent`/`failed`

## Workflow follow-up

- Archive the change after review and production verification.
- Confirm Firebase web push certificates/VAPID are configured if browser system notifications are required beyond inbox.
