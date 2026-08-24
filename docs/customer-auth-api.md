# Customer Auth API

## Feature overview
This feature covers customer registration, email verification, resend verification email, login, current user, and logout for the Befood-Bachelors E-Food backend.

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
1. Customer clicks verification link.
2. Backend validates uid and token (existing 24h token generator).
3. Backend activates the user.
4. Backend marks the profile as email verified.
5. Backend stores verification timestamp.

**Account registration complete** = successful email verification. Incomplete onboarding profile does **not** block login.

## Resend verification flow
If the user is unverified, the backend sends a fresh verification email. If already verified, the backend returns a helpful message. Unknown emails get a generic anti-enumeration message.

## Login flow
Customers login with email and password only. Login is blocked until email verification is completed. Login is **not** blocked for missing name/phone/occupation/`is_bachelor`/gender.

Login response may include additive `onboarding_completion` metadata.

## Logout flow
Authenticated users can logout by deleting the current DRF token.

## Current user flow
Authenticated users can fetch their own user and customer profile details, including:

- Extended completion: `customer_profile.profile_completed` / `profile_completion_percentage`
- Onboarding completion: top-level `onboarding_completion` (`completed`, `missing_fields`, `completion_percentage`)

These two completion concepts are separate.

## API endpoint list
- `POST /user_management/customer/register/`
- `GET /user_management/verify-email/<uidb64>/<token>/`
- `POST /user_management/resend-verification/`
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
