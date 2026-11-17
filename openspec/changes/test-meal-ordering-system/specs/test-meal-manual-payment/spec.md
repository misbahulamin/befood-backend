# Spec Delta

## Purpose

Admins record and correct manual Test Meal payments with an audit trail, keeping payment status independent of delivery status and separating confirmed order value from collected revenue.

## ADDED Requirements

### Requirement: Payment status independent of delivery status

Test Meal payment status MUST be independent of order/delivery status. Supported payment statuses for v1 MUST include at least `unpaid`, `paid`, and `refunded` when refunds are recorded. Partial payment MAY be deferred. An order MAY be delivered while still unpaid. Payment changes MUST NOT alter quota accounting.

#### Scenario: Delivered but unpaid allowed

- **WHEN** a Test Meal order is marked delivered and payment is still unpaid
- **THEN** both statuses coexist and the order remains outstanding for collection

#### Scenario: Marking paid does not change delivery status

- **WHEN** an admin records payment on a confirmed unpaid order
- **THEN** payment becomes paid and delivery/order fulfillment status is unchanged

### Requirement: Admin record payment

Verified admins MUST be able to record payment on an unpaid Test Meal order with collected amount, collection date, optional notes/reference, and the acting admin identity. Recording MUST be idempotent against duplicate payment records for the same order under normal retries. The system MUST use Decimal money fields and MUST NOT auto-mark paid from wallet or gateways.

#### Scenario: Record full payment

- **WHEN** a verified admin records payment equal to the order total on an unpaid order
- **THEN** payment status becomes paid and amount, date, admin, and optional notes are stored

#### Scenario: Non-admin denied

- **WHEN** a customer calls the record-payment endpoint
- **THEN** the system returns `401` or `403`

#### Scenario: Duplicate record prevented

- **WHEN** an admin retries an identical successful payment recording
- **THEN** the system does not create a second collected payment that double-counts revenue

### Requirement: Auditable payment corrections

Corrections to payment records (including marking refunded or fixing amount/date/notes) MUST leave an audit trail of who changed what and when. Silent overwrite without audit MUST NOT be allowed.

#### Scenario: Correction audited

- **WHEN** a verified admin corrects a previously recorded payment amount
- **THEN** the new values apply and an audit entry records actor, before/after, and timestamp

### Requirement: Revenue accounting split

Admin analytics and payment summaries MUST distinguish confirmed order value, collected payments, outstanding unpaid amount, unpaid order count, paid order count, and delivered-but-unpaid order count. Unpaid confirmed orders MUST NOT count as collected revenue. Payment collection MUST NOT affect Test Meal to subscription conversion flags.

#### Scenario: Outstanding equals confirmed minus collected

- **WHEN** confirmed Test Meal totals are `200.00` and collected payments are `70.00`
- **THEN** outstanding reported amount is `130.00`

#### Scenario: Unpaid not collected revenue

- **WHEN** an unpaid confirmed order exists for `69.84`
- **THEN** collected revenue excludes `69.84` while confirmed order value includes it
