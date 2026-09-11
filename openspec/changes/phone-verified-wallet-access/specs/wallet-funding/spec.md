## ADDED Requirements

### Requirement: Customer funding permission uses unified identity verification
The system SHALL treat a customer as permitted for manual wallet funding (recharge and withdraw submit) when `is_customer_identity_verified` (or equivalent) is true—including when trust comes only from phone verification. The system MUST NOT require email verification for phone-registered customers to submit funding requests. Unauthenticated callers MUST still receive `401`. Callers with no trusted identity factor MUST receive `403` for identity denial (distinct from funding kill-switch or frozen-wallet denials).

#### Scenario: Phone-verified customer may submit manual recharge
- **WHEN** an authenticated phone-verified customer with unverified email submits a valid manual recharge request
- **THEN** the system does not deny the request for email verification and applies the existing manual funding create rules

#### Scenario: Phone-verified customer may submit manual withdraw
- **WHEN** an authenticated phone-verified customer with unverified email submits a valid manual withdraw request
- **THEN** the system does not deny the request for email verification and applies the existing manual funding withdraw rules

#### Scenario: No trusted identity cannot submit funding
- **WHEN** an authenticated customer with no email, phone, or social identity verification submits recharge or withdraw
- **THEN** the system responds `403` for identity verification failure before creating a funding transaction
