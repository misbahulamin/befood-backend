# Client follow-ups: deferred registration + device tokens

Backend change: `registration-verify-before-create`.

## Mobile (`befood_mobile`) checklist

- [ ] After register → OTP verify → login, confirm `syncTokenIfNeeded()` still runs on login success.
- [ ] Cold start while logged in still syncs FCM token.
- [ ] Optional: send `device_token` + `platform` on `POST /user_management/login/` (backend accepts them).
- [ ] Web-created account → first mobile login → push still works after token sync.
- [ ] Subject line shows OTP; OTP screen UX unchanged.

## Frontend (`befood-frontend`) checklist

- [ ] Register modal → OTP modal flow unchanged (no permanent account until OTP succeeds).
- [ ] No device-token registration on web (expected).
- [ ] Copy still says verify email then login.
- [ ] Password reset OTP/subject still works (body design unchanged).

## Staging verification

1. Register with a deliberate wrong email → no `auth_user` row; only pending (or expired later).
2. Register with real email → OTP in subject → verify → user created → login OK.
3. Mobile login after web signup → `POST /notifications/device-token/` → admin push / test notification delivers.
4. `python manage.py cleanup_pending_registrations` removes expired pending only.
5. Password reset still confirms with OTP; subject starts with code.
