## Context

Customer registration (`auth_service.register_customer` → `send_activation_email`) and Delivery Man registration both email an `activation_link`. Today that link is built with Django `reverse(...)` + `request.build_absolute_uri(...)`, so the host equals the inbound API host (`api.befood.com.bd` in production). Password reset already builds links from `FRONTEND_URL` + `PASSWORD_RESET_FRONTEND_PATH` in `email_branding.py`.

Frontend SPA routes already exist:

- Customer: `/verify-email/:uidb64/:token` → page calls `GET /user_management/verify-email/{uid}/{token}/`
- Deliveryman: `/deliveryman/verify-email/:uidb64/:token` → page calls deliveryman verify API

Note: a path like `https://befood.com.bd/user_management/verify-email/...` would mirror the **API** path on the website origin; the SPA does **not** register that route. Email links must use SPA paths so React Router handles the click.

## Goals / Non-Goals

**Goals:**

- Activation email hrefs always use `{FRONTEND_URL}` + configurable SPA path (env-based; no hardcoded production domain in code).
- Never put `api.*` (or any request host) into customer/deliveryman verification email links.
- Preserve token generation, verify API behavior, and existing SPA verify pages.
- Align customer activation with the password-reset link pattern.

**Non-Goals:**

- Changing token algorithms, expiry, or verify endpoint URLs/methods.
- Proxying verify through nginx on the website domain as a substitute for SPA deep links.
- Reworking branded HTML templates beyond the link value they already receive.
- Forcing `FRONTEND_URL` default from `www` to apex in this change (ops may set env); document expected production value.

## Decisions

1. **Build activation links from `FRONTEND_URL`, not `request.build_absolute_uri`**
   - **Choice:** Add helpers (e.g. `build_activation_frontend_link` / deliveryman equivalent) that concatenate `FRONTEND_URL.rstrip('/')` + path + `/{uidb64}/{token}/`.
   - **Why:** Same proven pattern as `build_password_reset_link`; independent of which host hit the register/resend API.
   - **Alternatives:** Keep absolute URI and rewrite host via `EMAIL_SITE_URL` — still couples path to Django API `reverse` (`/user_management/...`), which does not match SPA routes.

2. **Use SPA paths, not API path prefixes on the website**
   - **Choice:** Defaults:
     - Customer: `/verify-email` → `{FRONTEND_URL}/verify-email/{uidb64}/{token}/`
     - Deliveryman: `/deliveryman/verify-email` → `{FRONTEND_URL}/deliveryman/verify-email/{uidb64}/{token}/`
   - Configurable via settings analogous to `PASSWORD_RESET_FRONTEND_PATH` (e.g. `EMAIL_VERIFICATION_FRONTEND_PATH`, `DELIVERYMAN_EMAIL_VERIFICATION_FRONTEND_PATH`).
   - **Why:** Matches `befood-frontend` `routes.ts`. User-facing “expected” URL that copies `/user_management/...` onto `befood.com.bd` would 404 in the SPA unless a new alias route is added; prefer matching existing frontend.
   - **Optional frontend follow-up (out of scope unless requested):** alias route `/user_management/verify-email/:uidb64/:token` redirecting to `/verify-email/...` for URL familiarity — not required if email uses SPA path.

3. **Drop `request` dependency from link building where practical**
   - **Choice:** Link builders take `user` only (uid/token); `send_*` may keep `request` for call-site compatibility but ignore it for href host.
   - **Why:** Avoid accidental regression to request host; simplifies tests with `@override_settings(FRONTEND_URL=...)`.

4. **Settings**
   - Reuse existing `FRONTEND_URL` (`config('FRONTEND_URL', ...)` in `core/settings/base.py`).
   - Add path settings with defaults matching frontend routes; never hardcode `https://befood.com.bd` in Python beyond existing defaults already present for other email brand fields.

## Risks / Trade-offs

- **[Risk] Wrong `FRONTEND_URL` in prod (still API or `www` mismatch)** → Mitigation: document required env; tests assert link starts with overridden `FRONTEND_URL` and does not contain `api.`; smoke with `send_test_auth_email`.
- **[Risk] Trailing-slash / path mismatch with React Router** → Mitigation: match frontend param style; trailing slash OK for static hosting if SPA fallback covers it; verify against live frontend route.
- **[Risk] Old emails still contain API links** → Mitigation: expected; only new emails change. API verify URL remains valid if someone opens an old link (direct API).
- **[Trade-off] User asked for `/user_management/verify-email/` on website** → We use `/verify-email/` to match shipped SPA; call out in implementation report.

## Migration Plan

1. Deploy backend with frontend-based activation links.
2. Confirm prod/staging `FRONTEND_URL` is the public website origin.
3. Register a test user / run `send_test_auth_email --type activation`; confirm href host/path.
4. Click link → SPA verify page → API success.
5. Rollback: revert link builders to `build_absolute_uri` (no schema migration).

## Open Questions

- None blocking: SPA path vs user-stated `/user_management/...` path is decided in favor of SPA (Decision 2). Confirm with product if an alias route on the frontend is desired later.
