## Why

Customer registration currently requires seven fields (email, name, phone, occupation, bachelor status, password) before the user can verify email and log in. This long upfront form increases drop-off and delays account activation. Splitting registration into **email verification first** and **progressive profile collection after login** reduces friction while preserving existing email verification and customer-only scope.

## What Changes

- Simplify `POST /user_management/customer/register/` so initial registration accepts only **email + password** (existing auth mechanism preserved); remove blocking requirements for name, phone, occupation, and `is_bachelor` at signup.
- Reuse the existing email verification system (`EmailVerificationTokenGenerator`, verify/resend endpoints, 24h expiry, activation semantics) without duplication or rewrite.
- Treat **email verification success** as account registration complete (`is_active=True`, login eligible); profile completeness remains a separate concern.
- Extend existing profile APIs (`GET/PATCH /user_management/customer/profile/`, `GET /user_management/me/`) to support **partial, immediate persistence** of progressive onboarding fields: `first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`, `gender`.
- Add **profile completion status** metadata (`missing_fields`, derived `completed` flag) so the frontend knows what to collect next without blocking login.
- Make `CustomerProfile.phone`, `occupation`, and `is_bachelor` **nullable** via backward-compatible migration; existing customer data is never reset.
- Enforce strict allow-list on profile PATCH to prevent mass assignment of privileged fields (`is_email_verified`, `profile_completed`, roles, etc.).
- **BREAKING (controlled rollout):** Registration request contract shrinks—clients sending legacy fields at signup must migrate or use a temporary compatibility window (see design).
- **Out of scope:** Admin, deliveryman, staff, vendor, or any non-customer registration/login flows; frontend modal timing; new email verification mechanism; new `marital_status` field (project uses `is_bachelor` today).

## Capabilities

### New Capabilities

- `customer-simplified-registration`: Email+password customer signup, existing verification reuse, verification-as-registration-complete semantics, backward-compatible rollout.
- `progressive-customer-profile`: Authenticated partial profile updates with immediate DB persistence, field-level validation, idempotency, and privileged-field protection.
- `customer-profile-completion-status`: Derived onboarding completion metadata exposed on `/me` and/or profile responses (`missing_fields`, `completed`).

### Modified Capabilities

- _(none)_ — no existing OpenSpec capability covers customer registration/auth; admin customer directory behavior is unchanged (reads existing stored fields).

## Impact

- **Models/migrations:** `user_management/models.py` — nullable `phone`, `occupation`, `is_bachelor` on `CustomerProfile`; no destructive data migration.
- **Services:** `auth_service.register_customer`, new or extended `profile_onboarding.py` (derived missing-fields logic).
- **Serializers/views:** `CustomerRegistrationSerializer`, `CustomerExtendedProfileUpdateSerializer`, `CurrentUserSerializer`, `CustomerExtendedProfileSerializer`, OpenAPI decorators.
- **URLs:** Existing `/user_management/customer/register/`, `/verify-email/`, `/resend-verification/`, `/login/`, `/me/`, `/customer/profile/` — no new duplicate endpoints unless PATCH contract requires serializer split.
- **Tests:** `test_customer_auth.py`, `test_customer_profile.py` — registration, verification, login-with-incomplete-profile, partial updates, security, legacy data preservation.
- **Docs:** `docs/customer-auth-api.md`, new/updated `user_management/docs/frontend/` progressive onboarding contract.
- **Clients:** Mobile/web registration screens must stop requiring profile fields at signup; post-login onboarding consumes completion status + PATCH profile.
- **Non-customer flows:** `deliveryman`, `admin` auth untouched.
