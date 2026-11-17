# Spec Delta

## ADDED Requirements

### Requirement: Frontend docs map total customer wallet liability card
The system SHALL update `admin_wallet/docs/frontend/admin-wallet.md` so an Admin Panel engineer can show total customer wallet liability on `/admin/wallet` without reading backend source. Docs MUST name the response field, map it to one overview card, state it is the sum of customer wallet balances (unconsumed prepaid credit), and contrast it with `net_customer_funding` (lifetime funding minus withdrawals, not reduced by meal spend).

#### Scenario: Engineer implements overview card from docs alone
- **WHEN** an Admin Panel engineer follows the updated frontend Admin Wallet documentation
- **THEN** they can bind the documented liability field from the existing dashboard (or summary) response to a single `/admin/wallet` overview card with the correct meaning versus Net customer funding

#### Scenario: Docs warn against reusing net customer funding for unconsumed prepaid
- **WHEN** an engineer reads the liability card section of the frontend docs
- **THEN** the docs state that `net_customer_funding` MUST NOT be used as the unconsumed prepaid total because meal consumption does not reduce that custody counter
