## ADDED Requirements

### Requirement: Monthly delivery-fee report for admins

The system SHALL provide a verified-admin monthly delivery-fee report endpoint accepting calendar `year` and `month`. The response MUST include at least: total delivery fee collected (sum of paid amounts for that month), total customers paid (count of distinct customers with paid status that month), and pending customers (count of customers with an active subscription who do not have a paid delivery-fee payment for that month). Amounts MUST be decimal money strings.

#### Scenario: September monthly totals

- **WHEN** a verified admin requests the monthly report for September 2026 after 83 customers paid totaling `25000.00` and 17 active subscribers remain unpaid for that month
- **THEN** the response includes collected `25000.00`, paid customers `83`, and pending customers `17`

#### Scenario: Month with no payments

- **WHEN** a verified admin requests a month with zero paid delivery-fee rows
- **THEN** collected amount is `0.00`, paid customers is `0`, and pending customers equals the count of active subscribers for the pending definition

### Requirement: Lifetime delivery-fee report for admins

The system SHALL provide a verified-admin lifetime delivery-fee report that returns at least: lifetime total amount collected (sum of all paid delivery-fee amounts) and total distinct customers who have at least one paid delivery-fee payment.

#### Scenario: Lifetime totals

- **WHEN** paid delivery-fee rows across history sum to `550000.00` across 650 distinct customers
- **THEN** the lifetime report returns total amount `550000.00` and total paid customers `650`

### Requirement: Only verified admins can read delivery-fee reports

Unauthenticated callers MUST receive `401`. Authenticated non-admin callers MUST be denied. Report endpoints MUST NOT expose other customers’ raw payment rows unless using the separate list endpoints with admin auth.

#### Scenario: Customer denied monthly report

- **WHEN** an authenticated customer requests the monthly delivery-fee report
- **THEN** the system denies access and does not return collection totals
