## ADDED Requirements

### Requirement: Verified admin can cancel a customer active subscription

The system SHALL expose a verified-admin HTTP API to cancel the target customer’s active `CustomerSubscription` by customer `public_id` under the existing admin customer web base path. The endpoint MUST require `IsVerifiedAdmin` (or equivalent verified-admin gate already used by `AdminCustomerViewSet`). The handler MUST invoke the canonical cancel domain service with `cancel_source=admin` and the authenticated admin user as cancelling actor. Non-admin customers and unverified admins MUST be denied. Frontend button visibility MUST NOT be treated as authorization.

#### Scenario: Authorized admin cancels active subscription

- **WHEN** a verified admin POSTs cancel for a customer who has an active subscription
- **THEN** the subscription becomes `cancelled`, cancellable slots are soft-skipped per canonical rules, and the response includes updated subscription status and wallet summary fields needed by admin UI

#### Scenario: Unverified or non-admin denied

- **WHEN** an authenticated non-admin or unverified admin calls the admin cancel endpoint
- **THEN** the request is rejected with forbidden (or unauthorized if unauthenticated) and no subscription or delivery state changes

#### Scenario: No active subscription

- **WHEN** a verified admin cancels for a customer with no active subscription
- **THEN** the API returns a clear not-found or business validation error and performs no delivery mutations

### Requirement: Admin cancel records actor audit metadata

When an admin cancels a subscription, the system MUST persist cancelling actor identity and cancel source on the subscription (additive fields such as `cancelled_by` and `cancel_source=admin`) and MUST remain compatible with the existing customer activity feed that surfaces `subscription_cancelled`. Optional reason text MAY be accepted when provided and stored in an existing note field or documented metadata without requiring a new audit framework table.

#### Scenario: Activity reflects admin cancellation

- **WHEN** an admin successfully cancels a subscription
- **THEN** subsequent admin customer activity includes a `subscription_cancelled` event for that subscription and the subscription record attributes the cancel to an admin source/actor

### Requirement: Admin cancel preview is available without mutating state

The system SHALL provide a verified-admin read preview for the same customer that classifies which meals would be cancelled vs preserved and estimates finalized meal liability and post-cancel `withdrawable_balance` using backend formulas. The preview MUST NOT change subscription status, delivery rows, or wallet balances.

#### Scenario: Preview matches subsequent cancel classification

- **WHEN** a verified admin requests cancel preview and then cancels without intervening meal-off setting or delivery changes
- **THEN** the sets of cancelled vs preserved meals in the cancel response match the preview classification

#### Scenario: Preview is read-only

- **WHEN** cancel preview is requested
- **THEN** no `CustomerSubscription` status change and no `OrderDelivery` status change occur
