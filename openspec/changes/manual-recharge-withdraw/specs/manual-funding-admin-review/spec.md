## ADDED Requirements

### Requirement: Verified admin can list and filter funding requests
The system SHALL provide a verified-admin API to list customer wallet funding requests (`type=recharge` or `type=withdraw`) with pagination and filtering by `status` (`pending`, `completed`, `failed`) and by `type`. Each list item MUST include at least request `public_id`, customer identity fields needed for review, `amount`, payment method when present, `transaction_id` for recharge provider refs, `status`, and `created_at`. Unauthenticated callers MUST receive `401 Unauthorized`. Authenticated non-admin or unverified-admin callers MUST receive `403 Forbidden`. Listing MUST remain available even when `WALLET_MANUAL_FUNDING_ENABLED` is false.

#### Scenario: Admin lists pending recharges
- **WHEN** a verified admin lists funding requests filtered by `type=recharge` and `status=pending`
- **THEN** the system responds `200` with only matching pending recharge requests

#### Scenario: Non-admin cannot list funding requests
- **WHEN** an authenticated customer calls the admin funding list endpoint
- **THEN** the system responds `403 Forbidden`

### Requirement: Verified admin can retrieve funding request detail
The system SHALL allow a verified admin to retrieve a funding request by `public_id` with full review/audit fields, including reviewer identity when present (`reviewed_by`), `reviewed_at`, and rejection reason. Missing ids MUST return `404 Not Found`. Detail MUST remain available when the customer funding kill switch is disabled.

#### Scenario: Admin retrieves pending withdraw detail
- **WHEN** a verified admin requests a pending withdraw by `public_id`
- **THEN** the system responds `200` with amount, status, customer identity, timestamps, and available audit fields

### Requirement: Verified admin can approve pending recharge
The system SHALL allow a verified admin (including an active superuser authorized by `IsVerifiedAdmin`) to approve a `pending` recharge through a funding-specific approve service. Approval MUST run atomically with consistent lock ordering: verify still pending under row lock, credit the customer wallet by the request amount, set status `completed`, set `reviewed_at` and `reviewed_by` to the acting User, and sync Admin Wallet custody credit. Approve/reject transitions are side-effect idempotent / exactly-once in effect: approving a non-pending request MUST return `409 Conflict` without changing balance or custody again. Wallet freeze after request creation MUST NOT by itself block admin approval of an already-pending recharge. Customer funding kill switch MUST NOT block this approve path.

#### Scenario: Approve pending recharge credits once
- **WHEN** a verified admin approves a pending recharge of `500.00`
- **THEN** the request becomes `completed`, customer balance increases by `500.00` exactly once, and review audit fields store the acting user and timestamp

#### Scenario: Second approve returns conflict without side effects
- **WHEN** a verified admin attempts to approve an already completed recharge
- **THEN** the system responds `409 Conflict` and the customer balance is unchanged by the second attempt

#### Scenario: Superuser without AdminProfile can approve and be recorded
- **WHEN** an active superuser without an `AdminProfile` approves a pending recharge
- **THEN** the request completes successfully and `reviewed_by` references that User

#### Scenario: Admin can approve after wallet frozen post-submit
- **WHEN** a pending recharge exists and the customer wallet is later frozen, then a verified admin approves the request
- **THEN** the approve is allowed and the customer wallet is credited according to the pending amount

#### Scenario: Non-admin cannot approve recharge
- **WHEN** an authenticated customer calls the recharge approve endpoint
- **THEN** the system responds `403 Forbidden`

### Requirement: Verified admin can reject pending recharge
The system SHALL allow a verified admin to reject a `pending` recharge through a funding-specific reject service. Rejection MUST set status `failed`, store `reviewed_at`/`reviewed_by`, accept an optional rejection reason, and MUST NOT credit the customer wallet or Admin Wallet custody. Rejecting a non-pending request MUST return `409 Conflict` without side effects. Rejection MUST remain available if the wallet is frozen after submission and when the customer funding kill switch is disabled.

#### Scenario: Reject pending recharge leaves balance unchanged
- **WHEN** a verified admin rejects a pending recharge with an optional reason
- **THEN** the request becomes `failed`, the reason is retained when provided, and customer balance is unchanged

#### Scenario: Second reject returns conflict without side effects
- **WHEN** a verified admin attempts to reject an already failed or completed recharge
- **THEN** the system responds `409 Conflict` and no additional balance or custody change occurs

### Requirement: Verified admin can approve pending withdraw
The system SHALL allow a verified admin to approve a `pending` withdraw after manual payout through a funding-specific approve service. Approval MUST run atomically with consistent lock ordering: verify still pending under row lock, set status `completed`, set review audit fields to the acting User, and debit Admin Wallet custody for the same amount via existing custody sync helpers. If Admin Wallet float is insufficient, approve MUST return `409 Conflict`, leave the request `pending`, leave the customer reservation in place, create no custody debit, and leave review audit fields unchanged. Approving a non-pending withdraw MUST return `409 Conflict` without further customer balance or custody change. Wallet freeze after request creation and a disabled customer funding kill switch MUST NOT block this approve path when float is sufficient.

#### Scenario: Approve pending withdraw finalizes once
- **WHEN** a verified admin approves a pending withdraw with sufficient Admin Wallet float
- **THEN** the request becomes `completed`, review audit fields are stored, and Admin Wallet custody is debited once

#### Scenario: Second withdraw approve returns conflict without side effects
- **WHEN** a verified admin attempts to approve an already completed withdraw
- **THEN** the system responds `409 Conflict` and does not apply a second custody debit

#### Scenario: Float shortfall leaves review fields untouched
- **WHEN** withdraw approve fails due to insufficient Admin Wallet float
- **THEN** `reviewed_by`, `reviewed_at`, and `rejection_reason` remain unchanged and the request stays `pending`

### Requirement: Verified admin can reject pending withdraw
The system SHALL allow a verified admin to reject a `pending` withdraw through a funding-specific reject service. Rejection MUST run atomically: verify still pending, restore the reserved amount to the customer wallet, set status `failed`, store review audit fields and optional reason, and MUST NOT debit Admin Wallet custody. Rejecting a non-pending withdraw MUST return `409 Conflict` without releasing reservation twice. Rejection MUST remain available if the wallet is frozen after submission and when the customer funding kill switch is disabled, so reserved funds can still be restored.

#### Scenario: Reject pending withdraw releases reservation
- **WHEN** a verified admin rejects a pending withdraw of `100.00`
- **THEN** the request becomes `failed` and the customer wallet balance increases by `100.00`

#### Scenario: Admin can reject reserved withdraw after wallet frozen
- **WHEN** a pending withdraw exists, the wallet is later frozen, and a verified admin rejects the withdraw
- **THEN** the reservation is restored to the customer wallet and the request becomes `failed`

#### Scenario: Second withdraw reject returns conflict without side effects
- **WHEN** a verified admin attempts to reject an already failed or completed withdraw
- **THEN** the system responds `409 Conflict` and the customer balance is not increased again
