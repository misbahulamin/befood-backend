## 1. Pending registration data model

- [x] 1.1 Add `PendingCustomerRegistration` model (email unique among pending, password hash, optional profile fields, OTP hash/attempts/expiry, link token fields, timestamps, `expires_at`)
- [x] 1.2 Create and review migration; add indexes needed for email lookup and expiry cleanup
- [x] 1.3 Register model in Django admin (read-only/safe fields) for support debugging

## 2. Deferred registration & verification services

- [x] 2.1 Refactor `register_customer` to upsert pending registration only (no `User`/`CustomerProfile` until verify); keep response contract `{ message, email }`
- [x] 2.2 Implement pending-scoped OTP issue/verify with same TTL, attempts, cooldown, and hourly caps as current auth OTP settings
- [x] 2.3 Implement pending-scoped verification link token generation/validation while preserving `GET /user_management/verify-email/<uidb64>/<token>/` URL shape
- [x] 2.4 Change OTP and link verify paths to atomically create active verified `User` + `CustomerProfile`, assign CUSTOMER group, and consume/delete pending row
- [x] 2.5 Update resend-verification / resend-otp to target pending registrations with anti-enumeration responses
- [x] 2.6 Adapt unverified-login / legacy inactive-user paths (compatibility or migrate-to-pending) so login never treats pending-only emails as accounts
- [x] 2.7 Add management command to delete expired pending registrations; document cron/ops usage

## 3. Email subject OTP formatting

- [x] 3.1 Update `templates/emails/customer_activation_subject.txt` to code-first format (`{{ otp_code }} is your sign-in verification code`)
- [x] 3.2 Update `templates/emails/customer_password_reset_subject.txt` to code-first format for password-reset OTP emails
- [x] 3.3 Ensure send paths pass `otp_code` into subject context; leave HTML/text body templates unchanged
- [x] 3.4 Smoke-check rendered subjects for activation and password-reset sends in tests or local mail outbox

## 4. Device token auth sync

- [x] 4.1 Confirm `register_device_token` upsert-by-token behavior matches specs; fix any duplicate/create gaps if found
- [x] 4.2 Add optional login request fields `device_token` + `platform` that call `register_device_token` after successful customer authentication (backward compatible when omitted)
- [x] 4.3 Keep dedicated `POST /notifications/device-token/` as the canonical upsert API; document that mobile MUST sync after login even when optional login fields are unused
- [x] 4.4 Add/adjust tests for first-token create, existing-token update, multi-device second token, and login-with-optional-token

## 5. API / OpenAPI / docs

- [x] 5.1 Update OpenAPI/schema notes for register, verify, resend, and optional login device-token fields
- [x] 5.2 Update backend docs under `user_management/docs/backend/` for deferred registration + subject changes
- [x] 5.3 Update frontend/mobile integration docs (`user_management/docs/frontend*` / `frontend-mobile`) for verify-then-account-exists and post-login device-token sync (web→mobile)
- [x] 5.4 Update `notifications/docs/` device-token notes for auth-time sync expectations

## 6. Tests & migration safety

- [x] 6.1 Add/update registration tests: pending-only on signup; no `User` until verify; re-register pending; email-taken for verified users
- [x] 6.2 Add/update verify OTP + link tests that assert account creation and pending consumption
- [x] 6.3 Add/update resend, expiry, cleanup, and login-with-pending-only rejection tests
- [x] 6.4 Add/update password-reset tests proving flow still works and subject formatting does not break send/confirm
- [x] 6.5 Define and implement legacy inactive unverified customer migration/cleanup strategy with tests
- [x] 6.6 Run focused auth + device-token test suites and fix regressions

## 7. Client follow-ups (sibling repos)

- [x] 7.1 Document required `befood_mobile` checks: post-login `syncTokenIfNeeded` always runs after first login following web signup; optional login `device_token` wiring if backend field ships
- [x] 7.2 Document required `befood-frontend` checks: register → OTP modal unchanged; no device-token on web; copy still matches verify-then-login
- [x] 7.3 Coordinate staging verification: wrong-email signup leaves no permanent user; correct OTP creates user; mobile login receives push after token sync
