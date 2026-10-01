## ADDED Requirements

### Requirement: Active subscription required for guest meal

The system SHALL allow Guest Meal preview and create only when `get_active_subscription(customer)` returns an active subscription for the authenticated customer. The system MUST reuse that canonical helper and MUST NOT invent a separate active-subscription definition. If the subscription is cancelled, expired, inactive, or missing, the system MUST reject the request with a clear client-safe error and MUST NOT debit the wallet or create a guest meal record.

#### Scenario: Active subscriber can order

- **WHEN** a verified customer with an active subscription requests a valid guest meal create
- **THEN** the system proceeds past the subscription eligibility check

#### Scenario: No active subscription rejected

- **WHEN** a verified customer with no active subscription requests guest meal create
- **THEN** the system rejects the request and creates neither a guest meal nor a wallet debit

#### Scenario: Cancelled subscription rejected

- **WHEN** a verified customer whose only subscription is cancelled requests guest meal create
- **THEN** the system rejects the request

### Requirement: Guest meal is bound to date and meal period

Every Guest Meal order MUST target a specific business `date` and `meal_period` of `lunch` or `dinner`. The system MUST validate that the period is covered by the subscription’s effective preference via existing `periods_for_meal_period(subscription.meal_period_snapshot)`. Dates and periods MUST use BeFood meal-off business timezone rules (typically Asia/Dhaka). Invalid date or meal period MUST be rejected.

#### Scenario: Lunch-only subscription rejects dinner guest meal

- **WHEN** an active lunch-only subscriber requests a guest meal for `dinner`
- **THEN** the system rejects the request as an unsupported meal slot

#### Scenario: Invalid meal period rejected

- **WHEN** a client sends `meal_period` other than `lunch` or `dinner`
- **THEN** the system rejects the request with a validation error

### Requirement: Canonical guest meal unit pricing

The system SHALL compute guest meal unit price as published slot `final_meal_price_snapshot` for the subscription package on that `date` + `meal_period`, plus the configured guest meal box price from settings. The system MUST resolve base price through the existing published-slot pricing path (`resolve_published_slot_for_delivery` or equivalent). The system MUST NOT hardcode package meal prices. If base price cannot be resolved, the system MUST reject with a clear error and MUST NOT create the order.

#### Scenario: Base plus box equals unit price

- **WHEN** the published lunch slot final price is `60.00` and box price is `10.00` and quantity is `2`
- **THEN** unit price is `70.00` and total is `140.00`

#### Scenario: Missing published price rejected

- **WHEN** no published slot final price exists for the requested package date and period
- **THEN** the system rejects the guest meal request without wallet debit

### Requirement: Pricing snapshots on create

On successful create, the system MUST persist immutable snapshots of `base_meal_price`, `box_price`, `unit_price`, `quantity`, and `total_amount` on the guest meal record. Later changes to package slot prices or settings box price MUST NOT alter historical guest meal amounts.

#### Scenario: Package price change does not rewrite history

- **WHEN** a guest meal was created with base `60.00` and later the published slot price becomes `80.00`
- **THEN** the stored guest meal base, unit, and total remain the original snapshotted values

### Requirement: Monthly guest meal quantity limit

The system SHALL enforce a calendar-month maximum guest meal quantity (default `10`) in the meal-off business timezone (Asia/Dhaka). The limit MUST be quantity-based (sum of ordered units), not merely order count. The system MUST compute used quantity from authoritative guest meal records in countable statuses and MUST reject a request whose quantity would exceed remaining capacity. Failed create attempts MUST NOT count. Concurrent requests MUST NOT both succeed when their combined quantity would exceed the limit.

#### Scenario: Cumulative quantity reaches limit

- **WHEN** a subscriber has already ordered guest quantities totaling `8` in the current Asia/Dhaka calendar month and requests quantity `3`
- **THEN** the system rejects because `11` would exceed the monthly limit

#### Scenario: Tenth unit allowed

- **WHEN** used quantity is `9` and the subscriber requests quantity `1` with sufficient wallet funds and valid eligibility
- **THEN** the system accepts and used becomes `10`

#### Scenario: Prior calendar month does not count

- **WHEN** guest meals were ordered in the previous Asia/Dhaka calendar month
- **THEN** those quantities MUST NOT reduce the current month’s remaining limit

### Requirement: Wallet debit with meal-stop floor

Guest meal create MUST debit the customer wallet through the canonical ledger debit service inside the same database transaction as guest meal persistence. After debit, remaining balance MUST satisfy the agreed meal-stop floor rule for guest purchase (product default: recharge balance after debit must remain at or above `meal_stop_threshold`). If the debit would violate the floor, the wallet is frozen, or funds are insufficient, the system MUST reject without creating a guest meal. If guest meal persistence fails, the wallet debit MUST roll back. Direct balance-field mutation outside the ledger is forbidden.

#### Scenario: Sufficient headroom above threshold

- **WHEN** recharge balance is `500.00`, meal_stop_threshold is `200.00`, and guest total is `250.00`
- **THEN** the create succeeds and the wallet ledger shows a completed debit of `250.00`

#### Scenario: Below threshold after purchase rejected

- **WHEN** recharge balance is `500.00`, meal_stop_threshold is `200.00`, and guest total is `350.00`
- **THEN** the system rejects the create and does not debit or create a guest meal

### Requirement: Cutoff and published slot eligibility

The system MUST reject guest meal create/preview when `is_past_meal_cutoff(service_date, meal_period)` is true, reusing the existing meal-off cutoff helper. The system MUST require a published applicable menu for the subscription package on that date/period. The system MUST NOT implement a separate guest-meal cutoff calculator.

#### Scenario: Past cutoff rejected

- **WHEN** business now is strictly after the lunch meal-off deadline for the requested lunch date
- **THEN** guest meal create for that lunch is rejected

#### Scenario: At deadline still eligible

- **WHEN** business now equals the meal-off deadline for the requested slot
- **THEN** guest meal ordering remains eligible with respect to cutoff (same rule as meal-off)

### Requirement: Quantity validation

Guest meal APIs MUST accept a positive integer `quantity`. Non-positive or non-integer values MUST be rejected. The system SHOULD enforce a documented per-request maximum not greater than the monthly limit remaining. Quantity MUST drive total price, box charge aggregation, monthly quota validation, and wallet debit amount.

#### Scenario: Quantity two doubles total

- **WHEN** unit price resolves to `70.00` and quantity is `2`
- **THEN** total debit amount is `140.00`

#### Scenario: Zero quantity rejected

- **WHEN** quantity is `0` or negative
- **THEN** the system rejects with a validation error

### Requirement: Customer guest meal APIs

The system SHALL expose authenticated customer endpoints to read monthly usage, preview pricing/eligibility without side effects, create a guest meal (debiting wallet), and list/retrieve the caller’s own guest meals by `public_id`. Clients MUST send only `date`, `meal_period`, and `quantity` for preview/create. The system MUST ignore/reject client-supplied user id, subscription id, prices, balances, or monthly used counts as authoritative input. Authorization MUST scope all reads/writes to the authenticated customer only.

#### Scenario: Usage payload

- **WHEN** a subscriber with `6` countable guest units this month requests usage
- **THEN** the response includes `monthly_limit`, `used_quantity`, and `remaining_quantity` consistent with server-side counts

#### Scenario: Preview does not debit

- **WHEN** a customer calls preview with a valid payload
- **THEN** the response includes pricing and eligibility fields and the wallet balance is unchanged

#### Scenario: Create revalidates after preview

- **WHEN** a customer successfully previewed an order and later calls create after the cutoff has passed
- **THEN** create rejects even though preview previously succeeded

#### Scenario: Cannot order for another customer

- **WHEN** customer A is authenticated and attempts to create a guest meal for customer B via body or path manipulation
- **THEN** the system creates at most a guest meal for customer A’s own subscription context and never for B

### Requirement: Idempotent guest meal create

The system SHALL accept an optional `Idempotency-Key` on guest meal create. Replaying the same key with the same effective payload for the same customer MUST return the original successful result without a second debit or second guest meal. Reusing the same key with a different payload MUST return `409 Conflict`. Concurrent duplicate requests without a key MUST still be protected by transactional locking so monthly quota and wallet cannot be bypassed.

#### Scenario: Idempotent replay

- **WHEN** a create with idempotency key `K` succeeds and the client retries create with the same key and payload
- **THEN** exactly one guest meal and one wallet debit exist for that purchase

#### Scenario: Concurrent quantity race blocked

- **WHEN** used quantity is `9` and two concurrent quantity=`1` creates race
- **THEN** at most one succeeds and monthly used does not exceed `10`
