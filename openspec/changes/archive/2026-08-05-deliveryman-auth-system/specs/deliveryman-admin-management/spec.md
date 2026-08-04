## ADDED Requirements

### Requirement: Admin can list Delivery Man accounts with pending filter
The system SHALL provide a verified-admin API to list Delivery Man (`RiderProfile`) accounts with pagination and filters for approval status and email-verification state. The default pending queue MUST include only profiles where email is verified and `approval_status` is `pending`. List items MUST expose `public_id`, name, email, phone, address, email-verification flags, approval status, verified flag, and created timestamps. Unauthenticated or non-admin callers MUST be rejected.

#### Scenario: Pending queue lists email-verified awaiting approval
- **WHEN** a verified admin requests the Delivery Man list filtered to pending (or the default pending view)
- **THEN** the system returns paginated Delivery Man profiles that are email-verified and awaiting approval, identified by `public_id`

#### Scenario: Unverified registrations are excluded from pending queue
- **WHEN** a Delivery Man has registered but has not verified email
- **THEN** that account MUST NOT appear in the pending-approval queue

#### Scenario: Non-admin cannot list Delivery Men
- **WHEN** an unauthenticated client or a non-verified-admin user requests the admin Delivery Man list
- **THEN** the system responds `401` or `403` as appropriate and does not return account data

### Requirement: Admin can view Delivery Man detail
The system SHALL allow a verified admin to retrieve a Delivery Man by `public_id` with full review fields (name, email, phone, address, email verification, approval status, verified timestamps, rejection reason/notes, and other stored registration fields). Unknown or inaccessible ids MUST return `404`.

#### Scenario: Detail by public_id
- **WHEN** a verified admin requests a Delivery Man detail by `public_id`
- **THEN** the system responds `200` with the full review fields for that account

#### Scenario: Unknown public_id
- **WHEN** a verified admin requests a Delivery Man `public_id` that does not exist
- **THEN** the system responds `404 Not Found`

### Requirement: Admin can approve a Delivery Man
The system SHALL allow a verified admin to approve a pending, email-verified Delivery Man. Approval MUST set `approval_status=approved`, `is_verified=True`, set `verified_at`, set `user.is_active=True`, and send a confirmation email notifying the Delivery Man that they may log in. Approving an already-approved account MUST be idempotent or return a clear conflict/success without corrupting state. Approving before email verification MUST be rejected.

#### Scenario: Approve pending account
- **WHEN** a verified admin approves an email-verified pending Delivery Man
- **THEN** the profile becomes verified/approved, the user becomes active, a confirmation email is sent, and the Delivery Man can subsequently log in

#### Scenario: Approve before email verification rejected
- **WHEN** a verified admin attempts to approve a Delivery Man whose email is not verified
- **THEN** the system rejects the approval and leaves login disabled

### Requirement: Admin can reject a Delivery Man
The system SHALL allow a verified admin to reject a Delivery Man account with an optional reason. Rejection MUST set `approval_status=rejected`, `is_verified=False`, keep or set `user.is_active=False`, record rejection metadata, and MUST prevent login. The system SHOULD notify the applicant by email when rejection notification is enabled for the deployment.

#### Scenario: Reject pending account
- **WHEN** a verified admin rejects a pending Delivery Man with an optional reason
- **THEN** the account is marked rejected, remains inactive for login, and cannot obtain a Delivery Man auth token

#### Scenario: Rejected account stays blocked on login
- **WHEN** a rejected Delivery Man attempts login with correct credentials
- **THEN** the system denies the token and returns the not-approved messaging defined by Delivery Man auth requirements

### Requirement: Admin can manage verified status
The system SHALL allow a verified admin to update verification/approval state for operational corrections (for example re-approve a previously rejected account, or revoke verification). Revoking verification MUST set `is_verified=False`, deactivate login (`is_active=False`), and block Delivery Man login. Re-approval MUST restore verified/active state and allow login.

#### Scenario: Revoke verification
- **WHEN** a verified admin revokes an approved Delivery Man’s verified status
- **THEN** the account can no longer log in as a Delivery Man until approved again

#### Scenario: Re-approve after rejection
- **WHEN** a verified admin approves a previously rejected but email-verified Delivery Man
- **THEN** the account becomes verified and active and can log in successfully

### Requirement: Django admin supports Delivery Man review
The system SHALL register the Delivery Man profile in Django admin so operators can list, filter by approval/email-verified state, view fields, and perform approve/reject (or equivalent verified toggles) that call the same service rules as the API where practical.

#### Scenario: Django admin lists pending Delivery Men
- **WHEN** an operator opens Django admin for Delivery Man profiles filtered to pending email-verified accounts
- **THEN** those accounts are visible with core identity fields for review
