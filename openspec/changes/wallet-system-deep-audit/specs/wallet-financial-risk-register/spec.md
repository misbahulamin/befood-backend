## ADDED Requirements

### Requirement: Risk classification
The financial risk register SHALL classify identified wallet/accounting risks into Critical, Medium, and Low severity.

#### Scenario: All severities present
- **WHEN** the risk register is reviewed
- **THEN** it MUST contain at least one Critical, one Medium, and one Low risk with impact and recommended remediation (plan-only)

### Requirement: Critical custody and commission risks
The risk register SHALL include Critical risks covering Admin Wallet float exhaustion, silent referral accrual failure, accidental double-count meal-payment admin credit, and non-ledger balance writes.

#### Scenario: Silent referral failure listed
- **WHEN** Critical risks are reviewed
- **THEN** swallowed referral exceptions after successful delivery/charge MUST appear with business impact and remediation guidance

#### Scenario: Double-count flag listed
- **WHEN** Critical risks are reviewed
- **THEN** enabling `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` or running legacy meal-payment cash reconcile MUST be listed as a Critical accounting risk under custody accounting

#### Scenario: Float shortage behavior documented
- **WHEN** Admin float shortage is reviewed
- **THEN** the register MUST document withdraw approve rollback vs referral FAILED behavior and customer impact

### Requirement: Medium operational gaps
The risk register SHALL include Medium risks for missing continuous ledger↔balance reconciliation, incomplete meal refund workflows, and dual funding API path confusion where applicable.

#### Scenario: Reconciliation gap listed
- **WHEN** Medium risks are reviewed
- **THEN** lack of continuous production reconciliation MUST be listed with remediation pointing to scheduled jobs or future changes

### Requirement: Production safety classification
The risk register or linked design SHALL classify candidate remediations as SAFE vs RISKY for a live production database with existing balances and history.

#### Scenario: Safe vs risky table present
- **WHEN** production safety is reviewed
- **THEN** config/docs/dead-code cleanup MUST be marked safer than migrations, historical rewrites, or balance recalculation

### Requirement: Analysis-only remediation
Risk remediations in this change SHALL be planning guidance only and MUST NOT require application code, migration, or production data mutation as part of completing the analysis change.

#### Scenario: No code required to close analysis
- **WHEN** a risk lists a Solution
- **THEN** implementing that Solution MAY be deferred to a future OpenSpec change and MUST NOT block completion of this analysis-only change
