## ADDED Requirements

### Requirement: Persist social provider identities for scalable linking
The system SHALL store social login bindings in a dedicated `SocialIdentity` (or equivalent) record with `user`, `provider`, and `provider_user_id`, with uniqueness on `(provider, provider_user_id)`. The `provider` field MUST use TextChoices including at least `google` and `facebook`, and MAY include a reserved `apple` value for future Sign in with Apple without implementing Apple login in this change.

#### Scenario: First social bind stored
- **WHEN** a customer authenticates with Google or Facebook for the first time on an account
- **THEN** the system persists a social identity row linking that provider user id to the customer `User` with the correct provider choice

### Requirement: Normalize identities before linking
The system MUST apply `normalize_email()` and `normalize_phone_number()` before comparing provider claims to existing customers for linking or duplicate detection.

#### Scenario: Email case does not block linking
- **WHEN** a provider asserts verified email `A@Example.com` and a local customer has verified `a@example.com`
- **THEN** the system links to that existing customer

### Requirement: Link social login by verified email before creating a duplicate
When a social provider returns a verified email that matches an existing customer whose email is verified (`CustomerProfile.is_email_verified=True`) after normalization, the system MUST attach the social identity to that existing user and log them in instead of creating a new user.

#### Scenario: Google links to existing email account
- **WHEN** a user previously registered and verified email `a@example.com` and later signs in with Google asserting verified email `a@example.com`
- **THEN** the system links Google to the existing user and issues a token for that user without creating a second account

### Requirement: Link social login by verified phone when email does not match
When email-based linking does not apply and a verified phone matches a customer with `is_phone_verified=True` for the same normalized phone, the system MUST attach the social identity to that existing user and log them in. The same priority applies when a phone-authenticated customer later links social via shared verified phone/email rules.

#### Scenario: Social links via verified phone
- **WHEN** social resolution finds no verified-email match but finds a verified phone match on an existing customer
- **THEN** the system links the provider identity to that customer and issues a token for that user

#### Scenario: Phone OTP user later matches existing email user via shared verified phone
- **WHEN** an existing email-verified customer already has the same normalized phone marked verified and a social or phone flow would otherwise create a duplicate
- **THEN** the system links to the existing customer instead of creating a second account

### Requirement: Refuse unsafe account takeover conflicts
The system MUST NOT overwrite or steal an existing social identity belonging to a different user. Conflicting bind attempts MUST fail with a conflict or validation error without changing the rightful owner’s binding.

#### Scenario: Provider id already bound to another user
- **WHEN** a social credential’s provider user id is already linked to user A and a session attempts to bind it to user B
- **THEN** the system rejects the operation and leaves user A’s binding unchanged
