## ADDED Requirements

### Requirement: Customer identity uses OR of trusted factors
The system SHALL treat a customer as identity-verified when at least one of the following is true: email verified, phone verified, Google social identity linked, or Facebook social identity linked. The system MUST NOT require email verification and phone verification together for login, wallet recharge, subscription, or other authenticated customer feature gates that use identity verification. Social factors remain part of the same OR rule.

#### Scenario: Email verified only is identity-verified
- **WHEN** a customer has `is_email_verified=True` and `is_phone_verified=False` and no requirement for social identity
- **THEN** `is_customer_identity_verified` / `verification_status.identity_verified` is true and wallet recharge and other identity-gated customer features MUST NOT deny for missing phone verification

#### Scenario: Phone verified only is identity-verified
- **WHEN** a customer has `is_phone_verified=True` and `is_email_verified=False`
- **THEN** `identity_verified` is true and identity-gated customer features MUST NOT deny for missing email verification

#### Scenario: Neither factor blocks verified features
- **WHEN** a customer has email and phone unverified and no trusted social identity
- **THEN** `identity_verified` is false and identity-gated features respond with identity denial (`403` or equivalent permission denial)

### Requirement: Soft phone prompt is not a hard identity block
The system SHALL continue to expose `phone_verification_required` as true when the customer’s phone is not verified. That flag MUST mean a soft client prompt to bind/verify phone and MUST NOT redefine identity verification as requiring phone when email or social identity already satisfies the OR rule. Backend feature permissions MUST key off identity verification, not off `phone_verification_required`.

#### Scenario: Email-verified user still gets soft phone flag
- **WHEN** an email-verified customer has not verified phone
- **THEN** `phone_verification_required` is true and `identity_verified` is also true

#### Scenario: Soft flag must not alone deny wallet
- **WHEN** `phone_verification_required` is true and `identity_verified` is true
- **THEN** customer wallet recharge permission MUST allow the request past the identity gate (subject to other funding rules)

### Requirement: Authenticated profile and me expose verification_status
Authenticated customer `GET /me/` (or equivalent current-user endpoint) and customer extended profile reads SHALL include `verification_status` with at least `email_verified`, `phone_verified`, `google_verified`, `facebook_verified`, and `identity_verified`, consistent with the auth success envelope builder. Clients MUST be able to refresh identity state after login without relying only on the initial auth response.

#### Scenario: Me returns identity_verified for email-only customer
- **WHEN** an authenticated email-verified, phone-unverified customer requests `/me/`
- **THEN** the response includes `verification_status.identity_verified` true and `phone_verification_required` true

#### Scenario: Me returns identity_verified for phone-only customer
- **WHEN** an authenticated phone-verified customer with unverified email requests `/me/`
- **THEN** the response includes `verification_status.identity_verified` true

### Requirement: Mobile hard-gate uses identity_verified only
Client documentation SHALL require mobile apps to allow verified features when `verification_status.identity_verified` is true, including when only one of email or phone is verified. Clients MUST NOT require `email_verified AND phone_verified`. Clients MUST NOT hard-block wallet recharge, subscription, or equivalent features solely because `phone_verification_required` is true. The Bangla identity-incomplete message MAY be shown only when `identity_verified` is false.

#### Scenario: Documented client rule for email-only
- **WHEN** mobile state shows `identity_verified=true`, `email_verified=true`, `phone_verified=false`, `phone_verification_required=true`
- **THEN** documented behavior allows Confirm Recharge submit without showing the identity-incomplete Bangla hard-block

#### Scenario: Documented client rule for phone-only
- **WHEN** mobile state shows `identity_verified=true`, `phone_verified=true`, `email_verified=false`
- **THEN** documented behavior allows verified features without requiring email verification first
