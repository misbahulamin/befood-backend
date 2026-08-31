## Why

Customers today can only verify email and reset password via deep links. Mobile users and many web users prefer entering a short OTP from email, and unverified registrants who try to log in only see a generic “verify your email” error without receiving a fresh verification message. Adding OTP alongside the existing link flows (without breaking them) improves React + Android UX and reduces support friction for accounts that never completed verification.

## What Changes

- Add a **customer auth OTP subsystem** used for email verification and password reset:
  - Hashed codes only (`code_hash` — never plaintext like `123456` in the DB)
  - Configurable expiry (default 10 minutes) and failed-attempt limits
  - **Resend cooldown** (default 60 seconds between OTP generation)
  - **Per-user hourly issue cap** (configurable)
  - Single-use, purpose isolation (verification ≠ password reset)
- Keep **existing link-based flows fully working** (verify-email link; password-reset request/validate/confirm; separate token generators)
- On registration, resend, and password-reset request: dual-channel email (**OTP + CTA link**), subject to cooldown/rate limits
- Public OTP APIs: verify-email OTP, resend OTP, password-reset request/validate/confirm OTP
- **Password-reset validate-otp** checks the code without consuming it and **does not grant reset permission**; **confirm-otp must independently re-verify** the OTP every time
- **Unverified login** (correct password): clear not-verified message; send verification email **or reuse** an active OTP already issued within the cooldown window (no email spam on repeated login)
- Client docs: OTP always supports **manual entry**; platform autofill is optional
- Automated tests for OTP, cooldown/rate limits, login reuse, confirm independence, and link regressions

## Capabilities

### New Capabilities
- `customer-auth-otp`: Shared OTP storage/hashing, expiry, attempt limits, resend cooldown, hourly issue cap, purpose isolation; email verification OTP verify/resend; password reset OTP request/validate/confirm (confirm re-verifies independently); dual-channel emails.
- `unverified-login-auto-verification`: Correct password + unverified → clear message; send dual-channel verification email unless an active OTP was issued within cooldown (reuse, no new mail).
- `auth-otp-api-docs`: Backend + frontend/mobile docs covering OTP + link, security (hash-only storage, cooldown, rate limits), manual OTP entry, and validate vs confirm semantics.

### Modified Capabilities
- (none in `openspec/specs/` — prior customer auth / password-reset work is not archived as main specs. This change owns OTP dual-channel requirements and must not break shipped link contracts.)

## Impact

- **Code:** `CustomerAuthOTP` + migration; `auth_otp` service; extend email verification / password reset services; serializers, views, URLs; templates; OpenAPI; tests.
- **APIs:** Additive public OTP routes; login behavior for unverified-but-correct credentials; existing link endpoints unchanged.
- **Email:** Activation and password-reset templates show OTP + button; throttled by cooldown/hourly caps.
- **Auth:** OTP confirm deletes DRF tokens (same as link confirm); purposes never mix.
- **Clients:** React + Android — manual OTP entry required in UX; autofill optional.
- **Out of scope:** Admin/deliveryman OTP; SMS; JWT migration; progressive onboarding profile rules.
