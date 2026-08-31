## Context

Customer auth already ships:

- Progressive registration → branded activation email with SPA deep link (`EmailVerificationTokenGenerator`, 24h)
- `GET /user_management/verify-email/<uidb64>/<token>/` and `POST /user_management/resend-verification/`
- Password reset request / validate / confirm via `PasswordResetTokenGenerator` + uidb64 (separate from activation)
- Login blocked until `CustomerProfile.is_email_verified`; message is only “Please verify your email before login.” — no automatic re-send
- Business logic in `user_management/services/`; public routes under `/user_management/`; DRF Token auth

Product needs **OTP + link** for both verification and password recovery (React + Android), without breaking link contracts, plus careful auto-resend on unverified login (no email spam).

Model field shapes in the product brief are guidance only; this design uses a **standard single purpose-scoped OTP table**.

## Goals / Non-Goals

**Goals:**

- Dual-channel (6-digit OTP + existing deep link) for email verification and password reset
- Secure OTP lifecycle: **HMAC-SHA256 `code_hash` only** (never plaintext in DB), configurable TTL (default 10 minutes), attempt limit, single-use, invalidate prior unused OTPs when a **new** code is issued
- **Resend cooldown** (default 60s) and **max OTP issues per user per purpose per hour** (configurable)
- Purpose isolation: verification OTP ≠ password-reset OTP
- `validate-otp` is UX-only (does not consume); **`confirm-otp` always re-verifies** — validate success alone never authorizes password change
- Unverified login with correct password → clear message + send verification email **or reuse** active OTP within cooldown (no new email)
- Clients must support **manual OTP entry**; autofill is optional platform behavior (documented)
- Backward-compatible link APIs; docs + tests

**Non-Goals:**

- Admin / deliveryman OTP or SMS OTP
- JWT migration
- Auto-login after verify or reset
- Global IP-based API gateway throttles beyond OTP issue cooldown/hourly caps (follow-up if needed)
- Changing progressive onboarding profile rules

## Decisions

### 1. Single `CustomerAuthOTP` model (purpose-scoped)

**Choice:** One model `CustomerAuthOTP`:

| Field | Role |
|-------|------|
| `user` | FK to `User` |
| `purpose` | `email_verification` \| `password_reset` |
| `code_hash` | HMAC-SHA256 digest — **only** form stored; never plaintext `123456` |
| `created_at` | Issue time (cooldown + hourly counting) |
| `expires_at` | Absolute expiry |
| `consumed_at` | Null until used |
| `attempt_count` | Failed verify attempts |
| `max_attempts` | From settings at issue time |

At most one **active** (unconsumed, unexpired) OTP per `(user, purpose)` when issuing a **new** code — prior actives invalidated.

**Alternatives considered:** Two near-duplicate tables — rejected; Redis-only — rejected for local/dev portability.

### 2. Cryptography, expiry, attempts, cooldown, hourly cap

**Choice:**

- Generate with `secrets` (6-digit numeric)
- Store `HMAC-SHA256(SECRET_KEY, code)` (or dedicated `AUTH_OTP_HMAC_KEY` later); compare via `hmac.compare_digest`
- Settings:
  - `AUTH_OTP_TTL_SECONDS` = `600` (10 min)
  - `AUTH_OTP_MAX_ATTEMPTS` = `5`
  - `AUTH_OTP_RESEND_COOLDOWN_SECONDS` = `60`
  - `AUTH_OTP_MAX_ISSUES_PER_HOUR` = configurable (e.g. `5` or `10` — pick a sane default at implement; document in API docs)
- On consume: set `consumed_at`
- On max attempts / expiry: reject; client must request again (subject to cooldown)

**Issue / resend policy:**

1. If an **active** OTP exists and `now - created_at < cooldown` → **do not** generate a new code and **do not** send another email; return success/generic message (and for login: still return not-verified). Optionally expose `retry_after` only where it does not harm anti-enumeration (prefer silent reuse for public resend).
2. If cooldown elapsed but hourly issue count for `(user, purpose)` would exceed cap → reject or return generic throttle message without leaking account existence where applicable.
3. Otherwise invalidate prior active OTPs, issue new hashed OTP, send email.

**Why:** Stops resend spam and login-driven inbox flooding while keeping OTP usable.

### 3. Service layer

**Choice:** `user_management/services/auth_otp.py` owns issue (with cooldown/cap), verify (non-consuming), consume, invalidate. Extend `send_activation_email` / password-reset send to obtain plaintext OTP **only in memory** for the email body, then persist hash only. Token generators stay untouched.

### 4. API surface

**Email verification**

| Method | Path | Role |
|--------|------|------|
| GET | `/user_management/verify-email/<uidb64>/<token>/` | Existing link verify |
| POST | `/user_management/verify-email/otp/` | `email` + `otp` → verify + consume |
| POST | `/user_management/resend-verification/` | Dual-channel; cooldown/cap applied |
| POST | `/user_management/verify-email/resend-otp/` | Alias of resend |

**Password reset**

| Method | Path | Role |
|--------|------|------|
| POST | `/user_management/password-reset/` | Request; dual-channel; anti-enumeration; cooldown/cap |
| POST | `/user_management/password-reset/request-otp/` | Alias of request |
| POST | `/user_management/password-reset/validate/` | Existing uid+token |
| POST | `/user_management/password-reset/confirm/` | Existing uid+token |
| POST | `/user_management/password-reset/validate-otp/` | Check OTP **without** consume — **UX only** |
| POST | `/user_management/password-reset/confirm-otp/` | **Independently** verify OTP again, then consume, set password, wipe DRF tokens |

**Confirm vs validate (critical):**

- `validate-otp` success MUST NOT be treated by clients as authorization to change password.
- Frontend MUST still collect OTP (or keep it) and send it on `confirm-otp`.
- Backend `confirm-otp` MUST re-check hash/expiry/attempts and consume in the same transaction as password change — never trust “already validated” client state.

Optional `X-Client-Type: web|mobile` — same payloads.

### 5. Unverified login auto-resend (cooldown reuse)

**Choice:** Correct password + unverified:

1. Return clear not-verified error (no token).
2. Call activation delivery helper with **`prefer_reuse_within_cooldown=True`**:
   - Active OTP within cooldown → **reuse** (no new OTP, no new email).
   - Else if hourly cap allows → issue new OTP + send email.
   - Else → skip send (still return not-verified); optional internal log.

Wrong password / unknown email → invalid credentials, **no** email.

### 6. Email templates

Show OTP + existing button/link on activation and password-reset templates. Plaintext OTP appears **only** in outbound email content, never in DB.

### 7. Documentation

- Backend: `user_management/docs/backend/email-verification-otp.md` — explicitly state DB stores `code_hash` only; cooldown; hourly cap; validate vs confirm.
- Frontend/mobile: `user_management/docs/frontend-mobile/auth-verification-integration.md` — **manual OTP entry always required in UX**; autofill optional; do not unlock password form on validate-otp alone; login not-verified + cooldown behavior.
- Cross-link `docs/customer-auth-api.md` and related docs.

### 8. Testing

Cover issue/verify/expiry/attempts; cooldown blocks new issue; hourly cap; login reuse vs send; validate does not consume; confirm without prior validate still works; confirm after validate still re-verifies; link regressions; emails contain OTP + link when a send occurs.

## Risks / Trade-offs

- **[Risk] OTP brute force** → Hash + short TTL + max attempts + cooldown/hourly caps.
- **[Risk] Login / resend email bombing** → Cooldown reuse for login; 60s resend cooldown; hourly issue cap.
- **[Risk] Clients treating validate-otp as authz** → Docs + confirm always re-verifies server-side.
- **[Risk] Anti-enumeration vs Retry-After** → Prefer generic messages on public resend/request; document cooldown for clients without leaking existence when possible.
- **[Trade-off] Reuse within cooldown means same code stays valid** → Acceptable; user already has the email; reduces spam.
- **[Trade-off] DB OTP vs Redis** → Migration cost; better portability.

## Migration Plan

1. Add model + settings + migration (additive).
2. Ship services, templates, routes.
3. Clients add OTP UI (manual entry) + deep links.
4. Rollback: disable new routes / hide OTP in templates; links remain.

## Open Questions

- None blocking. Default hourly cap chosen at implement time and documented (suggested starting value: `10` issues per user per purpose per rolling hour).
