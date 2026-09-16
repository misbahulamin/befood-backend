## 1. Service layer — validate & confirm

- [x] 1.1 Extend `user_management/services/password_reset.py` with helpers to resolve customer user from uidb64 and check reset token via existing `password_reset_token_generator`
- [x] 1.2 Implement `validate_password_reset(uidb64, token)` returning success/failure suitable for the validate API (no password change)
- [x] 1.3 Implement `confirm_password_reset(uidb64, token, new_password)` inside `transaction.atomic()`: validate token, `set_password`, save, delete all DRF `Token` rows for the user
- [x] 1.4 Ensure confirm applies Django `validate_password` (or rely on serializer) and rejects non-customer / invalid / expired tokens without mutating password

## 2. Serializers, views, URLs, OpenAPI

- [x] 2.1 Add `PasswordResetValidateSerializer` (`uid`, `token`) and `PasswordResetConfirmSerializer` (`uid`, `token`, `new_password`, `confirm_password` with match + `validate_password`)
- [x] 2.2 Add `PasswordResetValidateView` and `PasswordResetConfirmView` (AllowAny, thin; call services; OpenAPI under Customer Auth tag with examples)
- [x] 2.3 Register `POST password-reset/validate/` and `POST password-reset/confirm/` in `user_management/api/urls.py` next to existing request route
- [x] 2.4 Confirm existing `POST password-reset/` request contract remains unchanged (anti-enumeration message)

## 3. Tests

- [x] 3.1 Add tests for validate: valid token → 200; invalid/expired/malformed → 400; activation token rejected
- [x] 3.2 Add tests for confirm: success sets password; mismatch / weak password → 400; invalid token → 400; token reuse after success → 400
- [x] 3.3 Assert confirm deletes existing DRF Token and login works with new password (fails with old); keep/extend request anti-enumeration coverage as needed
- [x] 3.4 Run the new/related `user_management` password-reset tests and fix failures

## 4. Documentation

- [x] 4.1 Write `user_management/docs/backend/customer-password-reset.md` (full workflow, all endpoints, payloads, errors, field meanings, verify steps)
- [x] 4.2 Write `user_management/docs/frontend/customer-password-reset.md` (web + mobile integration, deep link, UX, no auto-login)
- [x] 4.3 Update branded-auth-emails backend/frontend docs to reference validate/confirm (remove “confirm is follow-up”)
- [x] 4.4 Cross-link password reset from `docs/customer-auth-api.md` endpoint list / flows
