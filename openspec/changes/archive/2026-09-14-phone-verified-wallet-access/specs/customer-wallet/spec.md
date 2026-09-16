## ADDED Requirements

### Requirement: Wallet read access allows phone-verified identity without email
The system SHALL allow an authenticated customer who is identity-verified via phone (without email verification) to retrieve their wallet summary and owned transaction list/detail under the same ownership and pagination rules as other verified customers. “Verified customer” for wallet read access MUST mean unified identity verification (phone or email or trusted social), not email-only.

#### Scenario: Phone-only verified customer reads wallet
- **WHEN** an authenticated customer with `is_phone_verified=True` and without email verification requests their wallet
- **THEN** the system responds `200` with that caller’s wallet summary and MUST NOT reject for missing email verification

#### Scenario: Phone-only verified customer lists transactions
- **WHEN** an authenticated phone-verified customer without email verification requests their wallet transaction list
- **THEN** the system responds `200` with a paginated list scoped to that caller’s wallet
