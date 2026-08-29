## 1. Settings and link helpers

- [x] 1.1 Add `EMAIL_VERIFICATION_FRONTEND_PATH` (default `/verify-email`) and `DELIVERYMAN_EMAIL_VERIFICATION_FRONTEND_PATH` (default `/deliveryman/verify-email`) in `core/settings/base.py` via `config()`, reusing existing `FRONTEND_URL`
- [x] 1.2 Add `build_activation_frontend_link(user)` (customer) in `email_branding.py` or `email_verification.py` using `FRONTEND_URL` + path + `/{uidb64}/{token}/` (mirror `build_password_reset_link`)
- [x] 1.3 Add deliveryman equivalent helper and wire `build_deliveryman_activation_link` / `send_deliveryman_activation_email` to stop using `request.build_absolute_uri`

## 2. Wire customer activation emails

- [x] 2.1 Update `build_activation_link` / `send_activation_email` in `email_verification.py` to use the frontend link helper (keep uid/token generation unchanged)
- [x] 2.2 Ensure register + resend paths keep calling `send_activation_email` without behavioral change beyond href

## 3. Tests

- [x] 3.1 Assert customer activation email body/HTML contains `{FRONTEND_URL}/verify-email/...` and does not use request `HTTP_HOST` / API-style absolute URI as the CTA origin (`test_branded_auth_emails.py` / customer auth tests)
- [x] 3.2 Assert deliveryman activation email uses `{FRONTEND_URL}/deliveryman/verify-email/...` (`test_deliveryman_auth.py` or email tests)
- [x] 3.3 Keep/confirm API verify success and invalid/expired token tests still pass unchanged

## 4. Docs and verification

- [x] 4.1 Update `user_management/docs/frontend/branded-auth-emails.md` (and backend doc if needed): activation email opens SPA path; SPA calls `GET /user_management/verify-email/...`
- [x] 4.2 Update deliveryman auth docs if they describe email href as the API absolute URL
- [x] 4.3 Run relevant unit tests; smoke with `send_test_auth_email --type activation` (or register) and confirm link format; click-through on frontend when env available
- [x] 4.4 Confirm production/staging `FRONTEND_URL` is website origin (e.g. `https://befood.com.bd`), not `https://api.befood.com.bd`
