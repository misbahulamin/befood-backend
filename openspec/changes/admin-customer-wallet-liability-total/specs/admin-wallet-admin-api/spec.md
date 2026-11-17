# Spec Delta

## ADDED Requirements

### Requirement: Dashboard and summary expose total customer wallet liability
The system SHALL include an additive decimal field on Admin Wallet summary and dashboard responses that equals the sum of all customer wallet `balance` values (prepaid unconsumed credit). The field MUST be distinct from `net_customer_funding`. Access control MUST remain verified-admin only. Empty wallet tables MUST return `0.00`.

#### Scenario: Dashboard returns live sum of customer balances
- **WHEN** a verified admin requests the Admin Wallet dashboard and customer wallets hold balances totaling `1500.00`
- **THEN** the response includes the total customer wallet liability field with value `1500.00` in addition to existing cash and funding fields

#### Scenario: Summary returns the same liability total
- **WHEN** a verified admin requests the Admin Wallet summary after the same wallets exist
- **THEN** the summary includes the same total customer wallet liability value as the dashboard

#### Scenario: Liability differs from net customer funding after meal spend
- **GIVEN** customers funded `1000.00` with no withdrawals and later spent `400.00` from wallets on meals
- **WHEN** a verified admin requests the Admin Wallet dashboard
- **THEN** `net_customer_funding` remains based on funding minus withdrawals and the total customer wallet liability equals the remaining sum of customer wallet balances (approximately `600.00` when no other credits/debits apply)

#### Scenario: Zero wallets yields zero liability
- **WHEN** a verified admin requests the Admin Wallet dashboard and no customer wallets exist
- **THEN** the total customer wallet liability field is `0.00`

#### Scenario: Non-admin cannot read liability total
- **WHEN** an authenticated customer requests the Admin Wallet dashboard or summary
- **THEN** the system denies access and does not return wallet or liability data
