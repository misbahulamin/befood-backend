## 1. OTP model and core service

- [x] 1.1 Add `CustomerAuthOTP` model (user, purpose, code_hash, created_at, expires_at, consumed_at, attempt_count, max_attempts) and register in admin as needed
- [x] 1.2 Add settings: `AUTH_OTP_TTL_SECONDS` (600), `AUTH_OTP_MAX_ATTEMPTS` (5), `AUTH_OTP_RESEND_COOLDOWN_SECONDS` (60), `AUTH_OTP_MAX_ISSUES_PER_HOUR` (configurable default e.g. 10)
- [x] 1.3 Create `user_management/services/auth_otp.py` with generate/hash/compare, issue with cooldown reuse + hourly cap, verify (non-consuming), consume, invalidate-by-purpose helpers (plaintext never persisted)
- [x] 1.4 Generate and apply migration for the new model

## 2. Email verification dual-channel

- [x] 2.1 Extend activation email send path to issue `email_verification` OTP (respect cooldown/cap) and pass `otp_code` + existing link into template context only when a new send occurs
- [x] 2.2 Update customer activation HTML/text templates to display OTP and keep verification button/link
- [x] 2.3 Add serializers + `POST /user_management/verify-email/otp/` view (email + otp → mark verified via existing `mark_email_verified`)
- [x] 2.4 Ensure `resend-verification` uses dual-channel send with cooldown/cap; add alias `POST /user_management/verify-email/resend-otp/` calling the same service
- [x] 2.5 Wire URLs and OpenAPI annotations for the new verification OTP endpoints

## 3. Password reset dual-channel

- [x] 3.1 Extend password-reset email send to issue `password_reset` OTP (respect cooldown/cap) and pass `otp_code` + reset link into templates when a new send occurs
- [x] 3.2 Update customer password-reset HTML/text templates to display OTP and keep reset button/link
- [x] 3.3 Add alias `POST /user_management/password-reset/request-otp/` sharing `request_password_reset` anti-enumeration + cooldown/cap behavior
- [x] 3.4 Add `validate-otp` (non-consuming, no authz) and `confirm-otp` (independently re-verify OTP, then password validators, consume, set password, delete DRF tokens)
- [x] 3.5 Wire URLs and OpenAPI annotations; leave existing uid+token validate/confirm unchanged

## 4. Unverified login auto-resend

- [x] 4.1 Update customer login so correct password + unverified returns clear not-verified error and triggers verification delivery with cooldown reuse (no new email if active OTP within cooldown)
- [x] 4.2 Ensure wrong credentials still return invalid-credentials without sending email

## 5. Documentation

- [x] 5.1 Write `user_management/docs/backend/email-verification-otp.md` (architecture, `code_hash`-only storage, cooldown, hourly cap, validate vs confirm, APIs)
- [x] 5.2 Write `user_management/docs/frontend-mobile/auth-verification-integration.md` (React + Android; manual OTP entry required; autofill optional; confirm must re-send OTP; deep links; cooldown UX)
- [x] 5.3 Update `docs/customer-auth-api.md` and cross-link from existing password-reset / branded-auth-email docs

## 6. Tests

- [x] 6.1 Tests: issue OTP, verify correct OTP, reject wrong/expired/exhausted OTP; resend within cooldown does not re-issue; hourly cap enforced
- [x] 6.2 Tests: password-reset request OTP, validate-otp does not consume, confirm-otp re-verifies without prior validate, reject reused OTP, DRF token wipe
- [x] 6.3 Tests: unverified login sends once then reuses within cooldown; wrong password does not send
- [x] 6.4 Regression: existing link email verification and link password-reset validate/confirm still pass; purpose isolation between OTP types
- [x] 6.5 Assert branded emails include both OTP and link when a new send occurs; assert plaintext OTP not stored on model rows
