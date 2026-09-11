## ADDED Requirements

### Requirement: Prioritized improvement backlog
The improvement roadmap SHALL prioritize finance/wallet controls into Must have now, Should have later, and Optional buckets.

#### Scenario: Three priority buckets present
- **WHEN** the roadmap section is reviewed
- **THEN** each of Must have now, Should have later, and Optional MUST contain at least two concrete items

### Requirement: Must-have operational controls
Must-have items SHALL include: disable/remove `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` double-count risk; automated wallet consistency verification; referral commission reconciliation monitoring; Admin Wallet float monitoring; and a production deploy checklist.

#### Scenario: Flag risk and float included
- **WHEN** Must have now is reviewed
- **THEN** meal-payment admin credit risk removal/disable AND float monitoring MUST both be listed

#### Scenario: Consistency and referral monitoring included
- **WHEN** Must have now is reviewed
- **THEN** automated consistency verification AND referral reconcile monitoring MUST both be listed

### Requirement: Future productized finance features
Should-have items SHALL cover finance dashboard, transaction export, refund/reversal workflow, and ledger reconciliation. Optional items SHALL cover event-sourced rebuild and provider webhook automation.

#### Scenario: Dashboard and refund listed
- **WHEN** Should have later is reviewed
- **THEN** finance dashboard and refund/reversal workflow MUST appear

#### Scenario: Optional advanced items listed
- **WHEN** Optional is reviewed
- **THEN** event-sourced rebuild and provider webhook automation MUST appear

### Requirement: Backward-compatible remediation constraint
Roadmap items that become future implementation work SHALL preserve existing customer balances and historical transactions; balance recalculation and historical rewrite MUST be excluded from Must-have remediation.

#### Scenario: No history rewrite in must-haves
- **WHEN** Must have now is reviewed
- **THEN** no item MUST require rewriting completed wallet or admin ledger history

### Requirement: No implementation in analysis phase
Completing the improvement roadmap artifact for this change SHALL NOT include shipping the listed features; items MUST be treated as inputs for future OpenSpec changes.

#### Scenario: Roadmap is planning output
- **WHEN** this change is marked analysis-complete
- **THEN** application code for roadmap features MUST remain unchanged by this change’s tasks
