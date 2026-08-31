# Customer Auth API

## Feature overview
This feature covers customer registration, email verification, resend verification email, login, current user, logout, and **password reset** for the Befood-Bachelors E-Food backend.

## Customer registration flow (simplified)
1. Customer submits **email** and **password** (required).
2. Optionally (compatibility window), clients may still send `first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`.
3. Backend validates uniqueness and format rules for any fields present.
4. Backend creates an inactive Django user (names may be empty).
5. Backend creates a `CustomerProfile` (phone / occupation / `is_bachelor` may be null).
6. Backend assigns the `CUSTOMER` group.
7. Backend sends the existing email verification link.

Profile fields that used to be required at signup are collected **after login** via progressive profile PATCH. See `user_management/docs/frontend/progressive-customer-onboarding.md`.

## Email verification flow
1. Customer receives branded email with a **6-digit OTP** and a verification link.
2. Customer either enters the OTP (`POST /user_management/verify-email/otp/`) or opens the link.
3. Backend validates OTP or uid+token (existing 24h token generator).
4. Backend activates the user, marks the profile email verified, and stores verification timestamp.

OTP details (cooldown, hashing, APIs): `user_management/docs/backend/email-verification-otp.md`  
Client guide: `user_management/docs/frontend-mobile/auth-verification-integration.md`

## Resend verification flow
If the user is unverified, the backend sends a fresh verification email when cooldown/hourly caps allow. Within cooldown, an active OTP is reused without another email. If already verified, the backend returns a helpful message. Unknown emails get a generic anti-enumeration message.

## Login flow
Customers login with email and password only. Login is blocked until email verification is completed. If credentials are correct but unverified, the API returns `code: email_not_verified` and may send (or reuse) a verification email. Login is **not** blocked for missing name/phone/occupation/`is_bachelor`/gender.

Login response may include additive `onboarding_completion` metadata.

## Logout flow
Authenticated users can logout by deleting the current DRF token.

## Password reset flow
Customers recover access without knowing the current password using **link and/or OTP**:

1. `POST /user_management/password-reset/` (or `.../request-otp/`) with email (anti-enumeration).
2. Open branded email: link `{FRONTEND_URL}/reset-password?uid=...&token=...` **and/or** enter OTP.
3. Link path: optional `POST .../password-reset/validate/` then `POST .../password-reset/confirm/`.
4. OTP path: optional `POST .../password-reset/validate-otp/` (UX only — does **not** authorize reset), then `POST .../password-reset/confirm-otp/` which **re-verifies** the OTP.
5. `POST /user_management/login/` with the **new** password.

Full OTP contract: `user_management/docs/frontend-mobile/auth-verification-integration.md`.  
Link reset: `user_management/docs/frontend/customer-password-reset.md`.

## Current user flow
Authenticated users can fetch their own user and customer profile details, including:

- Extended completion: `customer_profile.profile_completed` / `profile_completion_percentage`
- Onboarding completion: top-level `onboarding_completion` (`completed`, `missing_fields`, `completion_percentage`)

These two completion concepts are separate.

## API endpoint list
- `POST /user_management/customer/register/`
- `GET /user_management/verify-email/<uidb64>/<token>/`
- `POST /user_management/verify-email/otp/`
- `POST /user_management/resend-verification/`
- `POST /user_management/verify-email/resend-otp/`
- `POST /user_management/password-reset/`
- `POST /user_management/password-reset/request-otp/`
- `POST /user_management/password-reset/validate/`
- `POST /user_management/password-reset/validate-otp/`
- `POST /user_management/password-reset/confirm/`
- `POST /user_management/password-reset/confirm-otp/`
- `POST /user_management/login/`
- `GET /user_management/me/`
- `POST /user_management/logout/`

## Request examples
### Registration (minimal — preferred)
```json
{
  "email": "customer@example.com",
  "password": "StrongPassword123"
}
```

### Registration (legacy fields still accepted)
```json
{
  "email": "customer@example.com",
  "first_name": "Rahim",
  "last_name": "Uddin",
  "phone": "17XXXXXXXX",
  "occupation": "student",
  "is_bachelor": true,
  "password": "StrongPassword123"
}
```

### Login
```json
{
  "email": "customer@example.com",
  "password": "StrongPassword123"
}
```

### Resend verification
```json
{
  "email": "customer@example.com"
}
```

## Response examples
### Registration success
```json
{
  "message": "Registration successful. Please check your email to verify your account.",
  "email": "customer@example.com"
}
```

### Verification success
```json
{
  "message": "Email verified successfully. You can now login."
}
```

### Login success (excerpt)
```json
{
  "token": "<token>",
  "user": {
    "id": 1,
    "email": "customer@example.com",
    "first_name": "",
    "last_name": ""
  },
  "groups": ["CUSTOMER"],
  "customer_profile": {
    "phone": null,
    "occupation": null,
    "is_bachelor": null,
    "is_email_verified": true
  },
  "onboarding_completion": {
    "completed": false,
    "missing_fields": ["first_name", "last_name", "phone", "occupation", "is_bachelor", "gender"],
    "completion_percentage": 0
  }
}
```

### `/me` onboarding metadata
```json
{
  "user": { "id": 1, "email": "customer@example.com", "first_name": "", "last_name": "" },
  "groups": ["CUSTOMER"],
  "customer_profile": {
    "phone": null,
    "occupation": null,
    "is_bachelor": null,
    "is_email_verified": true,
    "gender": null,
    "profile_completion_percentage": 0,
    "profile_completed": false
  },
  "onboarding_completion": {
    "completed": false,
    "missing_fields": ["first_name", "last_name", "phone", "occupation", "is_bachelor", "gender"],
    "completion_percentage": 0
  },
  "is_authenticated": true
}
```

## Client migration notes
1. Stop requiring profile fields on the signup screen.
2. After verify + login, read `onboarding_completion.missing_fields` from `/me` or login.
3. Collect missing fields via `PATCH /user_management/customer/profile/` in small steps.
4. Do not block login for incomplete onboarding.

## Validation notes
- Email unique (case-insensitive), stored lowercase
- Password must pass Django validators
- Phone (when provided): exactly 10 digits, unique among customers
- Occupation (when provided): existing `CustomerProfile.Occupation` choices
- Privileged fields (`is_email_verified`, roles, `is_active`) cannot be set via registration
