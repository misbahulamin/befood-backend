## Why

Customer (and Delivery Man) activation emails currently embed links built with `request.build_absolute_uri()`, so the host is the API host (`api.befood.com.bd`). Users must never see the backend API domain in email CTAs; verification deep links should open the public website, then the SPA calls the existing verify API.

## What Changes

- Change customer activation link generation to use `FRONTEND_URL` + a configurable frontend path (same pattern as password reset), not the request host / Django `reverse` absolute URI.
- Change Delivery Man activation link generation the same way (frontend deliveryman verify route).
- Keep backend verify endpoints, token generators, and email templates’ CTA variable names unchanged.
- Update tests and frontend/backend auth email docs so activation links document the website URL, not the API host.
- **Not BREAKING** for API clients: verify endpoints stay at `/user_management/verify-email/...` and `/user_management/deliveryman/verify-email/...`. Only the **email href** host/path changes to match SPA routes.

## Capabilities

### New Capabilities

- `email-verification-frontend-links`: Activation emails MUST use the configured frontend website base URL and SPA verify paths so users never see `api.*` hosts in verification links.

### Modified Capabilities

- `deliveryman-auth`: Clarify that the verification **email** deep link targets the frontend SPA path; the public API verify endpoint remains available for the SPA to call.

## Impact

- Backend: `user_management/services/email_verification.py`, `user_management/services/deliveryman_email.py`, optionally `email_branding.py` + settings (`FRONTEND_URL`, new path settings).
- Tests: branded auth emails, customer auth, deliveryman auth link assertions.
- Docs: `user_management/docs/frontend|backend/branded-auth-emails.md`, deliveryman auth docs if they describe email hrefs.
- Frontend: no required code change if links use existing routes (`/verify-email/:uidb64/:token`, `/deliveryman/verify-email/:uidb64/:token`); production `FRONTEND_URL` env must point at the public site (e.g. `https://befood.com.bd`).
- Ops: ensure staging/prod `FRONTEND_URL` is the website origin, not the API origin.
