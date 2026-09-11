## ADDED Requirements

### Requirement: Client branches on identifier existence before referral UI
Mobile (and any customer auth client) MUST call the backend existence/pre-check APIs before showing referral input. Referral input MUST appear only when the entered email or phone is not an existing customer identifier. Existing customers MUST proceed to login or OTP without a referral section.

#### Scenario: Existing email skips referral
- **WHEN** the user enters an email that email-check reports as an existing verified customer
- **THEN** the client shows login (password / existing auth) and does not show referral input

#### Scenario: New email may show referral
- **WHEN** the user enters an email that is not an existing verified customer (new or pending registration path)
- **THEN** the client MAY show referral input once for that first registration

#### Scenario: Existing phone skips referral
- **WHEN** phone check indicates the phone already exists on a customer
- **THEN** the client runs phone OTP login only and does not show referral input

### Requirement: After email or social login, phone uses authenticated bind
When auth success returns `phone_verification_required=true` (or equivalent), the client MUST keep the session and collect phone via authenticated bind OTP endpoints. The client MUST NOT start an anonymous phone registration flow that can create a second account or re-prompt referral as a new signup.

#### Scenario: Email success then phone bind
- **WHEN** a new or existing email/social session requires phone verification
- **THEN** the client calls bind send/verify with the auth token and updates the same account

#### Scenario: Referral not shown on post-login phone step
- **WHEN** the user is already authenticated and completing phone verification
- **THEN** the client does not display referral code input

### Requirement: Documented endpoint map for identity-safe auth
Backend frontend documentation MUST describe the ordered flows for: (1) new email + referral + later bind phone, (2) new phone + referral, (3) existing email login, (4) existing phone login, (5) social login + bind phone. Docs MUST name the exact paths for email-check, phone check-availability, phone OTP verify, and phone bind verify, and MUST warn that anonymous verify after email login causes duplicate-account risk.

#### Scenario: Docs cover bind vs anonymous verify
- **WHEN** integrators read the customer auth frontend doc after this change
- **THEN** the doc clearly distinguishes bind endpoints from anonymous phone create-or-login and states when referral is allowed

### Requirement: Subscription and wallet continuity across identifiers
For a single linked customer, logging in with email or phone MUST expose the same subscriptions, wallet, delivery history, and referral profile. Clients MUST NOT assume a new local account after adding a second identifier.

#### Scenario: Same wallet after phone bind
- **WHEN** a customer with an existing subscription and wallet binds a phone and later logs in with that phone
- **THEN** the client receives the same customer identity and the same wallet/subscription data
