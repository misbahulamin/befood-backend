## ADDED Requirements

### Requirement: End-to-end money flow documentation
The audit report SHALL document customer recharge, meal payment, withdrawal, referral commission, and Admin Wallet custody flows, including services, tables, transaction types, and status transitions (`pending`, `completed`, `failed`, `cancelled` where applicable).

#### Scenario: Recharge flow documented
- **WHEN** a stakeholder reads the wallet system audit report
- **THEN** the report MUST describe pending request → approve/reject → customer bucket credit → Admin Wallet `customer_funding` credit with named services and models

#### Scenario: Meal payment debit order documented
- **WHEN** the meal payment section is reviewed
- **THEN** the report MUST state that meal debits use commission-first then recharge, and MUST explain the business rationale

#### Scenario: Withdrawal bucket restriction documented
- **WHEN** the withdrawal section is reviewed
- **THEN** the report MUST state that only `recharge_balance` is withdrawable and commission cannot be withdrawn on coded paths

### Requirement: Locked final accounting model
The audit report SHALL document the locked custody accounting model: recharge credits admin; meal payment does not change admin; withdraw debits admin; referral debits admin and credits customer commission.

#### Scenario: Meal leaves admin unchanged
- **WHEN** the locked accounting table is reviewed
- **THEN** meal payment MUST show Admin Wallet as NO CHANGE while customer wallet is debited commission-first

### Requirement: Meal-payment admin credit flag analysis
The audit report SHALL analyze `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` usage, removal safety, production impact, historical-data impact, and whether a migration is required.

#### Scenario: Flag usage inventoried
- **WHEN** Issue 1 analysis is reviewed
- **THEN** the report MUST list settings, ingestion gate, legacy reconcile command, and confirm meal hot path does not call `credit_from_meal_payment`

#### Scenario: Removal is data-safe
- **WHEN** removal safety is reviewed
- **THEN** the report MUST state that disable/remove is app/config-safe, MUST NOT rewrite historical rows, and MUST NOT require a balance migration

### Requirement: Production-safe remediation plan
The audit report SHALL include a phased safe implementation plan (ops harden → future code cleanup → monitoring) under live-production constraints.

#### Scenario: Phased plan present
- **WHEN** the safe implementation plan is reviewed
- **THEN** Phase A/B/C MUST appear with explicit bans on historical rewrite and balance recalculation

### Requirement: Dual-bucket invariant analysis
The audit report SHALL evaluate whether `balance == recharge_balance + commission_balance` is maintained on all production money paths and SHALL identify any paths that can break the invariant.

#### Scenario: Impossible balance example addressed
- **WHEN** the balance calculation section is reviewed
- **THEN** the report MUST explain whether a wallet with `balance=1000`, `recharge_balance=700`, `commission_balance=200` can occur on service paths and what guards exist

### Requirement: Ledger mutation inventory
The audit report SHALL list production call sites that change customer or admin wallet balances, including file, function, purpose, and risk level.

#### Scenario: Mutation list present
- **WHEN** the ledger audit section is reviewed
- **THEN** the report MUST include a mutation inventory covering `wallet.services.ledger`, `wallet.services.funding`, meal payment, referral commission, and admin wallet operations

### Requirement: Industry comparison and ratings
The audit report SHALL compare BeFood wallet practices to common fintech wallet controls and MUST provide numeric ratings out of 10 for Wallet Architecture, Accounting Safety, and Scalability.

#### Scenario: Ratings published
- **WHEN** the industry comparison section is reviewed
- **THEN** three ratings out of 10 MUST be present with brief justification

### Requirement: Scale-readiness executive answer
The audit report SHALL answer whether BeFood can scale while keeping money accountable under the current wallet system, with explicit Good / Problem / Risk and Immediate / Future recommendations.

#### Scenario: Executive summary present
- **WHEN** leadership reads the final business report section
- **THEN** the section MUST include current status (good/problem/risk), immediate recommendations, future recommendations, and a clear scale-readiness verdict

### Requirement: Analysis phase does not mutate production
Completing this change SHALL NOT modify application code, create migrations, or change production wallet data.

#### Scenario: No implementation side effects
- **WHEN** this analysis change is completed
- **THEN** existing customer balances and historical transactions MUST remain unchanged by the change itself
