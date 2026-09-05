## ADDED Requirements

### Requirement: Unified customer identity verification helper

The system SHALL provide a central helper `is_customer_identity_verified(user)` in `user_management.services.identity_verification` that returns true when the customer has at least one trusted identity: `CustomerProfile.is_email_verified`, `CustomerProfile.is_phone_verified`, a Google `SocialIdentity` for the user, or a Facebook `SocialIdentity` for the user. Customer feature permission and business-rule gates that previously required email verification MUST call this helper (or an equivalent shared function that uses the same rule) and MUST NOT require `is_email_verified` alone. The helper MUST be structured so future providers (for example Apple or WhatsApp) can be added in one place without changing every gate call site.

#### Scenario: Email-verified customer is identity-verified

- **WHEN** a customer has `is_email_verified=True` and no phone or social verification
- **THEN** `is_customer_identity_verified` returns true

#### Scenario: Phone-verified customer is identity-verified

- **WHEN** a customer has `is_phone_verified=True` and `is_email_verified=False` with no social identities
- **THEN** `is_customer_identity_verified` returns true

#### Scenario: Google-linked customer is identity-verified

- **WHEN** a customer has a `SocialIdentity` with provider `google` and email/phone flags are false
- **THEN** `is_customer_identity_verified` returns true

#### Scenario: Facebook-linked customer is identity-verified

- **WHEN** a customer has a `SocialIdentity` with provider `facebook` and email/phone flags are false
- **THEN** `is_customer_identity_verified` returns true

#### Scenario: Unverified email-only customer is not identity-verified

- **WHEN** a customer has `is_email_verified=False`, `is_phone_verified=False`, and no Google or Facebook `SocialIdentity`
- **THEN** `is_customer_identity_verified` returns false

### Requirement: Customer feature gates use identity verification for authenticated customers only

The system SHALL enforce identity verification (via the unified helper) before authenticated customer actions that currently require email verification for access, including at least: order placement validation, subscription creation, and the `IsVerifiedCustomer` permission class. Identity verification checks MUST run only for authenticated customers. Guest or anonymous users MUST continue existing guest checkout, location, or other guest-supported behavior and MUST NOT be newly blocked by this identity gate. When the gate fails for an authenticated customer, the system MUST return a client-safe English error such as “Identity verification is required before placing an order.” (or equivalent identity-oriented wording) and MUST NOT use “Email verification is required…” for these gates. Successful authentication with a verified phone or social identity MUST be sufficient to pass these gates without email verification.

#### Scenario: Phone OTP customer can place an order

- **WHEN** an authenticated customer with `is_phone_verified=True` and `is_email_verified=False` attempts to place an order (or an action guarded by `IsVerifiedCustomer`)
- **THEN** the identity gate allows the request (subject to other non-identity business rules)

#### Scenario: Google OAuth customer can subscribe

- **WHEN** an authenticated customer with a Google `SocialIdentity` and `is_email_verified=False` attempts to subscribe
- **THEN** the identity gate allows the request (subject to other non-identity business rules)

#### Scenario: Facebook OAuth customer can place an order

- **WHEN** an authenticated customer with a Facebook `SocialIdentity` and `is_email_verified=False` attempts to place an order
- **THEN** the identity gate allows the request (subject to other non-identity business rules)

#### Scenario: Existing email-verified customer unchanged

- **WHEN** an authenticated customer with `is_email_verified=True` attempts to place an order or subscribe
- **THEN** the identity gate allows the request as before

#### Scenario: Unverified email-only customer remains blocked

- **WHEN** an authenticated customer with no verified email, phone, Google, or Facebook identity attempts to place an order or subscribe
- **THEN** the system rejects the request with an identity-verification error (not an email-only requirement message)

#### Scenario: Guest flows are not newly gated by identity verification

- **WHEN** a guest or anonymous client uses an existing guest-supported checkout or location flow
- **THEN** the request is not rejected solely because `is_customer_identity_verified` is false or missing for a non-authenticated principal

### Requirement: Auth responses expose verification_status

All successful customer auth envelopes produced by the shared auth response builder (email login, phone OTP, Google OAuth, Facebook OAuth, and equivalent session issuance paths) MUST include a `verification_status` object with boolean fields `email_verified`, `phone_verified`, `google_verified`, `facebook_verified`, and `identity_verified`, where `identity_verified` matches `is_customer_identity_verified(user)`. Existing auth fields such as `customer_profile.is_email_verified` and `customer_profile.is_phone_verified` MUST remain present for backward compatibility. Auth and related response builders MUST safely handle phone-only users whose `user.email` is null or empty (MUST NOT call string operations such as `.lower()` on a null email).

#### Scenario: Phone auth response shows identity verified

- **WHEN** a customer completes phone OTP login/registration with `is_phone_verified=True`
- **THEN** the auth response includes `verification_status.phone_verified=true` and `verification_status.identity_verified=true`

#### Scenario: Phone-only user with null email does not crash auth response

- **WHEN** a phone-authenticated customer has null or empty `user.email`
- **THEN** the auth response builds successfully and returns an empty or omitted email per existing API conventions without raising an error

#### Scenario: Google auth response shows google and identity verified

- **WHEN** a customer completes Google OAuth login/registration with a linked Google identity
- **THEN** the auth response includes `verification_status.google_verified=true` and `verification_status.identity_verified=true`

#### Scenario: Facebook auth response shows facebook and identity verified

- **WHEN** a customer completes Facebook OAuth login/registration with a linked Facebook identity
- **THEN** the auth response includes `verification_status.facebook_verified=true` and `verification_status.identity_verified=true`

### Requirement: Provider identity and email ownership remain separate

After successful phone OTP verification the system MUST persist `CustomerProfile.is_phone_verified=True` (and timestamp when applicable). After successful Google or Facebook OAuth linking/login the system MUST persist the corresponding `SocialIdentity` row, which is sufficient for `google_verified` / `facebook_verified` and thus `identity_verified`. The system MUST NOT set `is_email_verified=True` solely because social login succeeded or because a provider returned an email string. The system MAY set `is_email_verified=True` only when product policy explicitly trusts a provider-asserted verified email claim. Email verification OTP/link flows MUST continue to set `is_email_verified=True` and MUST remain available.

#### Scenario: Phone OTP sets phone verified

- **WHEN** a new or existing customer successfully verifies a phone OTP that completes auth
- **THEN** the customer profile has `is_phone_verified=True` and identity verification succeeds

#### Scenario: Social login grants identity without requiring email_verified

- **WHEN** a customer completes Google or Facebook OAuth and a `SocialIdentity` is stored while `is_email_verified` remains false
- **THEN** `identity_verified` is true and authenticated customer feature gates allow access

#### Scenario: Email verification system remains available

- **WHEN** an email-only customer completes email OTP or link verification
- **THEN** the system sets `is_email_verified=True` and identity verification succeeds without removing the email verification endpoints or pending-registration email finalize flow

### Requirement: Documentation reflects multi-provider identity gates

Backend and frontend multi-provider auth documentation MUST state that customer feature access requires `identity_verified` (any one provider), that email verification remains for email ownership/recovery/messaging, that gate API errors use identity-oriented English copy, and that clients SHOULD present Bangla UI messaging for failed identity gates (for example: “আপনার অ্যাকাউন্ট যাচাই সম্পন্ন হয়নি। দয়া করে একটি যাচাইকৃত মাধ্যম দিয়ে অ্যাকাউন্ট নিশ্চিত করুন।”). Documentation MUST instruct clients not to block phone/social users solely on email verification.

#### Scenario: Frontend docs describe identity_verified and Bangla UI

- **WHEN** a client integrator reads the multi-provider auth frontend documentation
- **THEN** the docs describe `verification_status.identity_verified`, the English API identity error wording, recommended Bangla UI copy, and instruct clients not to force email verification for phone/Google/Facebook users
