# Spec Delta

## Purpose

Defines corrected prepaid Guest Meal eligibility, pricing, monthly quota, wallet debit, and customer preview/create/usage APIs for active subscribers, including the mandatory personal Meal-OFF gate.

## ADDED Requirements

### Requirement: Active subscriber required for Guest Meal

The system MUST allow Guest Meal preview and create only for a verified customer with an active meal subscription. Non-subscribers and customers without an active subscription MUST be rejected without wallet debit or Guest Meal creation.

#### Scenario: Non-subscriber rejected

- **WHEN** a verified customer without an active subscription calls Guest Meal preview or create
- **THEN** the system rejects the request with a domain eligibility error and creates no Guest Meal and no wallet debit

#### Scenario: Active subscriber may proceed past subscription gate

- **WHEN** a verified customer with an active subscription requests a Guest Meal for a covered meal period
- **THEN** the subscription gate passes and further eligibility rules are evaluated

### Requirement: Personal Meal-OFF blocks Guest Meal for the same slot

The system MUST reject Guest Meal preview and create when the customer’s regular meal for the same `service_date` and `meal_period` is personally OFF (`OrderDelivery` `skipped` + `skip_source=customer`). Lunch and dinner MUST be independent. Rejection MUST use `PERSONAL_MEAL_OFF` (HTTP 422) with no Guest Meal, wallet debit, or quota change.

#### Scenario: Lunch OFF blocks Guest Lunch only

- **WHEN** the customer’s lunch delivery for date `D` is customer-skipped and dinner for `D` is scheduled
- **THEN** Guest Lunch for `D` is rejected with `PERSONAL_MEAL_OFF` and Guest Dinner for `D` remains eligible with respect to this rule

#### Scenario: Dinner OFF blocks Guest Dinner only

- **WHEN** the customer’s dinner delivery for date `D` is customer-skipped and lunch for `D` is scheduled
- **THEN** Guest Dinner for `D` is rejected with `PERSONAL_MEAL_OFF` and Guest Lunch for `D` remains eligible with respect to this rule

#### Scenario: Both periods OFF block both Guest Meals

- **WHEN** lunch and dinner for date `D` are both customer-skipped
- **THEN** Guest Lunch and Guest Dinner for `D` are both rejected with `PERSONAL_MEAL_OFF`

#### Scenario: System skip is not personal Meal-OFF

- **WHEN** the customer’s lunch delivery for date `D` is skipped with `skip_source=system` and is not customer meal-off
- **THEN** the personal Meal-OFF gate does not reject Guest Lunch solely for that system skip

#### Scenario: Create revalidates Meal-OFF after preview

- **WHEN** preview succeeds while lunch is ON and the customer then turns lunch OFF before create
- **THEN** create rejects with `PERSONAL_MEAL_OFF` and does not debit the wallet

### Requirement: Guest Meal date, period, cutoff, and price gates

The system MUST reject past service dates, unsupported meal periods relative to the subscription preference, requests after the meal-off cutoff for that slot, and requests without a published applicable slot price. Create MUST revalidate these gates inside the same atomic transaction as debit and persist.

#### Scenario: Past date rejected

- **WHEN** a customer requests a Guest Meal for a service date before business today
- **THEN** the system rejects the request without debit or create

#### Scenario: Cutoff passed rejected

- **WHEN** business now is strictly after the meal-off deadline for the requested slot
- **THEN** preview and create reject with a cutoff domain error and do not debit

#### Scenario: Missing published price rejected

- **WHEN** no published slot final meal price exists for the subscription package on that date and period
- **THEN** preview and create reject without debit or create

### Requirement: Guest Meal pricing snapshots and prepaid wallet debit

The system MUST price each guest unit as published slot final meal price plus configured guest box price, snapshot base/box/unit/total on the Guest Meal, ignore client-supplied prices, debit the wallet exactly once on successful create, enforce the meal-stop recharge floor (`recharge_balance − total >= meal_stop_threshold`), reject frozen wallets and insufficient funds, and roll back debit and create together on failure. Preview MUST NOT debit.

#### Scenario: Successful create debits exact total

- **WHEN** an eligible create request succeeds for quantity `N`
- **THEN** one completed wallet debit equals snapshotted `unit_price × N` and the Guest Meal stores matching price snapshots

#### Scenario: Preview does not debit

- **WHEN** preview succeeds for an eligible request
- **THEN** no wallet transaction is created and monthly quota is unchanged

#### Scenario: Meal-OFF rejection does not debit

- **WHEN** create is rejected for `PERSONAL_MEAL_OFF`
- **THEN** no wallet transaction is created and wallet balances are unchanged

#### Scenario: Meal-stop floor rejection

- **WHEN** `recharge_balance − total` would be strictly below `meal_stop_threshold`
- **THEN** create is rejected without creating a Guest Meal

### Requirement: Monthly Guest Meal quota and idempotency

The system MUST enforce the configured calendar-month quantity limit from countable Guest Meal statuses, serialize concurrent creates so the limit cannot be exceeded, and treat Idempotency-Key same payload as replay without a second debit while same key with different payload returns conflict.

#### Scenario: Monthly limit exceeded

- **WHEN** remaining monthly quantity is less than requested quantity
- **THEN** create is rejected and monthly used quantity is unchanged

#### Scenario: Idempotent replay same payload

- **WHEN** create is retried with the same Idempotency-Key and same date, period, and quantity
- **THEN** the original Guest Meal is returned and the wallet is not debited again

#### Scenario: Idempotency payload conflict

- **WHEN** create reuses an Idempotency-Key with a different date, period, or quantity
- **THEN** the system returns HTTP 409 conflict and does not create a second Guest Meal
