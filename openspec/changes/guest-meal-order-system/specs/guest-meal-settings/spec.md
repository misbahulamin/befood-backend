## ADDED Requirements

### Requirement: Configurable guest meal box price

The system SHALL store guest meal one-time box price on the existing order-wallet settings singleton (or equivalent admin settings resource already used for meal-stop thresholds). The default value MUST be `10.00` BDT unless operations change it. Guest meal pricing MUST read the live settings value at order time and snapshot it onto the guest meal record. Application code MUST NOT hardcode the box price as an undeclared business constant outside settings defaults/migrations.

#### Scenario: Admin-updated box price applies to new orders

- **WHEN** an admin sets guest meal box price to `15.00` and a subscriber later creates a guest meal
- **THEN** the new order’s box price snapshot is `15.00` and unit price uses that box amount

#### Scenario: Historical orders keep prior box snapshot

- **WHEN** a guest meal was created with box `10.00` and settings later change to `15.00`
- **THEN** the historical guest meal retains box snapshot `10.00`

### Requirement: Configurable monthly guest meal limit

The system SHALL store the monthly guest meal quantity limit in the same settings singleton, defaulting to `10`. Create and usage APIs MUST enforce the configured limit. Changing the limit MUST affect future eligibility calculations only and MUST NOT rewrite historical guest meal records.

#### Scenario: Default monthly limit is ten

- **WHEN** settings have not been customized
- **THEN** guest meal usage reports `monthly_limit` of `10`

#### Scenario: Raised limit allows additional units

- **WHEN** an admin raises the monthly limit to `12` and a subscriber has used `10` countable units this month
- **THEN** the subscriber may order up to `2` additional units subject to other eligibility rules
