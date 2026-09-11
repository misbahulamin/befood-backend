## ADDED Requirements

### Requirement: Phone-only identity is valid for customer features

The system SHALL treat a customer as identity-verified when at least one of the following is true: phone is verified, email is verified, or an approved social login link exists. The system MUST NOT require a non-empty `User.email` for account activity, subscription, or delivery-slot generation. Phone-only registration MUST continue to create accounts with blank email and `is_phone_verified=True`.

#### Scenario: Phone-only customer is identity-verified

- **WHEN** a customer has `is_phone_verified=True`, blank email, and `is_email_verified=False`
- **THEN** identity verification succeeds and subscribe/delivery flows MUST treat the customer as verified

#### Scenario: Email-only customer remains valid

- **WHEN** a customer has verified email and no phone
- **THEN** identity verification succeeds unchanged

### Requirement: Email must not gate subscription eligibility

Subscribe APIs and permissions MUST use identity verification (phone or email or social). The system MUST NOT reject subscribe solely because `User.email` is blank or `is_email_verified` is false when phone verification is present.

#### Scenario: Phone-verified customer can subscribe

- **WHEN** a phone-verified customer with blank email meets plan and wallet gates and calls subscribe
- **THEN** the system creates an ACTIVE subscription (subject to existing single-active-subscription rules)

#### Scenario: Unverified identity cannot subscribe

- **WHEN** a customer has neither verified phone nor verified email nor social identity
- **THEN** the system rejects subscribe with an authentication/permission error
