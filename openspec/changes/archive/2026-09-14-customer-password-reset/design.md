## Context

Customer password recovery is partially shipped:

- `POST /user_management/password-reset/` + branded email + `PasswordResetTokenGenerator` + frontend deep link (`FRONTEND_URL` + `PASSWORD_RESET_FRONTEND_PATH?uid=&token=`) already exist in `user_management/services/password_reset.py`.
- Confirm / set-new-password API is explicitly deferred in frontend docs.
- Auth is DRF **Token** authentication (not JWT). Customer identity uses Django `User` + `CustomerProfile`.
- Email verification uses a **separate** `EmailVerificationTokenGenerator`; reset tokens must stay isolated.
- Business logic belongs in `services/`; views stay thin; public auth routes live under `/user_management/` (not `/api/v1/`).

Frontend and mobile need a complete, documented flow: request → open email link → (optional validate) → confirm → login again.

## Goals / Non-Goals

**Goals:**

- Production-ready customer confirm path: validate uid+token, set new password with Django validators, invalidate DRF tokens.
- Preserve existing request endpoint contract (anti-enumeration message).
- Reuse existing token generation / email helpers — no duplicate reset token system.
- Ship backend + frontend/mobile API docs covering the full workflow.
- Tests covering happy path and common failure modes.

**Non-Goals:**

- Admin or deliveryman forgot-password.
- Migrating auth to JWT / SimpleJWT.
- Changing branded email HTML/layout (unless a tiny copy fix is required).
- Rate limiting infrastructure beyond what the project already has (note as follow-up if absent).
- Auto-login after reset (client must call existing login).

## Decisions

### 1. Extend `password_reset.py` service; thin APIViews

**Choice:** Add `validate_password_reset_token(uidb64, token)` and `confirm_password_reset(uidb64, token, new_password)` in `user_management/services/password_reset.py`. New serializers + `APIView`s in existing `serializers.py` / `views.py`; wire URLs next to the request route.

**Alternatives considered:** Separate `password_reset_views.py` module — deferred; current auth surface fits in `views.py`. Django `auth_views.PasswordResetConfirmView` — rejected; project uses DRF JSON APIs, not form views.

**Why:** Matches existing request-email pattern and project layering.

### 2. Endpoints and URL shape

**Choice:**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/user_management/password-reset/` | Existing request (unchanged) |
| POST | `/user_management/password-reset/validate/` | Check `uid` + `token` before showing form |
| POST | `/user_management/password-reset/confirm/` | Set new password |

Use JSON body fields `uid` (uidb64 from email query), `token`, and for confirm also `new_password` + `confirm_password`.

**Alternatives considered:** Path params like verify-email (`.../<uidb64>/<token>/`) — rejected for confirm because password belongs in body; validate as GET — rejected to avoid tokens in access logs/proxies as query strings on API host (email link already uses query on frontend; API validate should POST body).

**Why:** Aligns with SPA reading query params then POSTing to API; keeps secrets out of server access logs for validate/confirm.

### 3. Token validation rules

**Choice:** Resolve user via `urlsafe_base64_decode(uid)` → `User` with `customer_profile`. Accept only when `password_reset_token_generator.check_token(user, token)` succeeds. Rely on Django `PASSWORD_RESET_TIMEOUT` (default 3 days unless settings override). Do **not** accept activation tokens.

**Why:** `check_token` already embeds password hash + timeout; changing password invalidates outstanding reset tokens automatically.

### 4. Password rules and response shape

**Choice:** Reuse `django.contrib.auth.password_validation.validate_password` (same as registration). Require `new_password == confirm_password`. Success confirm returns `200` with a short message (no auth token). Failures: `400` with field errors for mismatch/weak password; invalid/expired uid+token → `400` with a stable non-leaky detail (e.g. `token` / `uid` errors or `detail`), without revealing whether the email exists beyond what uid decoding already implies.

**Why:** Consistent with registration validators; avoid auto-issuing tokens so clients always go through login (and email-verified gate).

### 5. Session invalidation after reset

**Choice:** Inside `transaction.atomic()`, `user.set_password(...)`, `user.save()`, then `Token.objects.filter(user=user).delete()`.

**Why:** DRF tokens do not rotate with password hash; wipe prevents continued access with a stolen prior token.

### 6. Eligibility

**Choice:** Same as request: only users with `customer_profile`. Do not require `is_email_verified` for reset itself; login remains blocked until verified (existing behavior).

**Why:** Avoid inventing new gates; unverified users may still need to recover password before completing verification UX.

### 7. Documentation

**Choice:**

- Backend: `user_management/docs/backend/customer-password-reset.md` (full technical + workflow).
- Frontend/mobile: `user_management/docs/frontend/customer-password-reset.md` (integration-first).
- Update `branded-auth-emails` docs to remove “confirm is follow-up”.
- Cross-link from `docs/customer-auth-api.md`.

**Why:** Matches project doc conventions and the explicit product ask for client-ready API docs.

## Risks / Trade-offs

- **[Risk] Enumerate via validate/confirm on guessed uids** → Mitigation: opaque uidb64 + cryptographically checked tokens; generic invalid-token errors; no email in error payloads.
- **[Risk] Email link token appears in browser history** → Mitigation: frontend should strip query params after reading; document for SPA/mobile deep-link handlers.
- **[Risk] No dedicated rate limit on request endpoint** → Mitigation: document as known gap / follow-up; keep anti-enumeration; do not block this change on a new throttle framework.
- **[Trade-off] No auto-login after confirm** → Extra login call; clearer security and consistent verified-email gate.
- **[Trade-off] Validate endpoint is optional for clients** → Confirm remains authoritative; validate is UX-only.

## Migration Plan

1. Deploy backend with new validate/confirm routes (additive, non-breaking).
2. Keep request endpoint response identical.
3. Frontend/mobile: wire reset page to validate + confirm; then login.
4. Rollback: remove/disable new routes if needed; request+email remains usable but incomplete without confirm (current production gap).

No DB migrations expected (stateless Django tokens).

## Open Questions

- None blocking implementation. Default Django `PASSWORD_RESET_TIMEOUT` is acceptable unless product later requests a shorter window (document actual setting value in API docs at implement time).
