## ADDED Requirements

### Requirement: Commission accrues only on charged delivered meals
The system SHALL attempt referral commission accrual when an `OrderDelivery` transitions to `delivered` and the meal wallet charge completes successfully. Commission MUST NOT accrue for skipped, missed, or uncharged deliveries. Accrual MUST run after the meal charge path used by admin mark and auto-delivery.

#### Scenario: Charged delivery for referred customer triggers accrual check
- **WHEN** a referred customer’s delivery is marked delivered and charged
- **THEN** the referral commission service evaluates eligibility for that delivery

#### Scenario: Meal-off skip does not create commission
- **WHEN** a referred customer’s delivery is skipped
- **THEN** the system creates no successful referral commission for that delivery

### Requirement: Both parties must have active subscriptions at accrual time
The system SHALL credit commission only when, at accrual time, the referred customer has a stored referrer relationship, the referrer has an active meal subscription, and the referred customer has an active meal subscription. If either party lacks an active subscription, the system MUST record status `skipped` (with reason) and MUST NOT create a successful money movement for that delivery.

#### Scenario: Both active yields commission
- **WHEN** both referrer and referred have active subscriptions and a referred meal is charged at `100.00` with default `5%`
- **THEN** the system records a commission of `5.00` with status `success`

#### Scenario: Referrer inactive skips commission
- **WHEN** the referred customer consumes a charged meal but the referrer has no active subscription
- **THEN** the system does not credit the referrer wallet and records `skipped`

#### Scenario: Referred inactive skips commission
- **WHEN** a delivery charge would otherwise qualify but the referred customer has no active subscription at accrual time
- **THEN** the system does not create a successful commission credit and records `skipped`

### Requirement: ReferralCommission uses an explicit status machine
The system SHALL store each commission attempt with status one of `pending`, `success`, `failed`, `skipped`, or `reversed`, plus a machine-readable status reason. `success` means Admin Wallet debit and referrer commission credit completed. `failed` means money movement could not complete (including Admin Wallet float shortfall) and MAY be retried by reconcile. `skipped` means business-rule exclusion without payout. `reversed` means a prior `success` was undone via the reversal flow.

#### Scenario: Float shortfall marks failed
- **WHEN** eligibility passes but Admin Wallet cannot cover the commission debit
- **THEN** the commission row status is `failed`, the referrer is not credited, and meal delivery is not blocked

#### Scenario: Amount below minimum marks skipped
- **WHEN** computed commission rounds to less than `0.01`
- **THEN** the system records `skipped` and does not move money

### Requirement: Commission money movement is atomic and audited
The system SHALL compute commission as a percentage of `OrderDelivery.charged_amount` using the configured default rate of `5%` unless overridden by settings. A successful accrual MUST, in one database transaction: debit the platform Admin Wallet by the commission amount, credit the referrer’s commission wallet bucket by the same amount, and persist a `ReferralCommission` audit row containing referrer, referred, delivery, meal date, meal price, percentage, commission amount, Admin Wallet debit reference, customer wallet credit reference, and status `success`. Rounding MUST use half-up to two decimal places.

#### Scenario: Successful commission updates both wallets and audit row
- **WHEN** eligibility passes for a charged meal priced `100.00` at `5%`
- **THEN** Admin Wallet decreases by `5.00`, referrer commission balance increases by `5.00`, and a `success` `ReferralCommission` row stores the full audit fields

### Requirement: Duplicate successful commission for the same delivery is impossible
The system SHALL enforce at most one `success` commission per `OrderDelivery` using a uniqueness constraint and wallet idempotency key derived from the delivery public id. Concurrent accrual attempts MUST NOT double-pay.

#### Scenario: Repeated accrual is idempotent
- **WHEN** commission accrual is invoked twice for the same charged delivery
- **THEN** only one successful commission credit and one Admin Wallet debit occur

### Requirement: Commission credits never increase withdrawable recharge balance
The system SHALL credit referral commission exclusively to the referrer’s `commission_balance` using wallet transaction type `referral_commission`. Commission credits MUST NOT be recorded as customer funding custody on the Admin Wallet.

#### Scenario: Commission credit lands in commission bucket
- **WHEN** a `5.00` referral commission is credited
- **THEN** the referrer’s `commission_balance` increases by `5.00`, `recharge_balance` is unchanged, and total `balance` increases by `5.00`

### Requirement: Successful commissions can be reversed with linked wallet transactions
The system SHALL support reversing a `success` `ReferralCommission` into status `reversed` by debiting the referrer’s `commission_balance` (or handling insufficient commission bucket per documented policy), crediting Admin Wallet for the reversal amount, and linking reversal wallet transactions to the original commission. Reversal MUST require a reason and actor audit fields. A commission MUST NOT be reversed twice. Reversal support MUST exist as a service (and admin-triggerable action) even if automatic delivery-cancel wiring is completed later.

#### Scenario: Admin reverses a successful commission
- **WHEN** a verified admin reverses a `success` commission of `5.00` with a reason
- **THEN** the commission becomes `reversed`, referrer `commission_balance` decreases by `5.00` when sufficient, Admin Wallet is credited `5.00`, and linked reversal transactions are stored

#### Scenario: Second reverse is rejected
- **WHEN** a commission already in `reversed` status is reversed again
- **THEN** the system rejects the operation without additional money movement

### Requirement: Admin can post manual referral adjustments
The system SHALL allow a verified admin to create a manual referral commission adjustment with a signed amount (+/−), required reason, target referrer (and optional referred/delivery context), producing audited wallet movement against the commission bucket and Admin Wallet, with a `ReferralCommission` row marked as manual and status `success` or `reversed` as appropriate to the sign.

#### Scenario: Manual positive adjustment credits commission bucket
- **WHEN** an admin posts a manual adjustment of `+10.00` with a reason for a referrer
- **THEN** the referrer `commission_balance` increases by `10.00`, Admin Wallet debits `10.00`, and an audited manual commission row is stored
