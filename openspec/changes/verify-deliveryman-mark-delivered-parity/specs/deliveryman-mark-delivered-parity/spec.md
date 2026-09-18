## ADDED Requirements

### Requirement: Deliveryman mark-delivered shares the auto-delivery completion pipeline

The system SHALL complete a deliveryman mark-delivered request through the same domain path used by auto meal delivery: `mark_delivery_and_notify` → `mark_delivery` → wallet charge (`charge_delivered_meal`) with delivery-scoped idempotency, best-effort Onahar and referral hooks, and best-effort customer FCM on a real transition to `delivered`. The only intentional differences MUST be the confirming actor (`marked_by` rider user vs cron `None`), optional rider note, and deliveryman-only zone authorization. The system MUST NOT implement a separate wallet debit or status-transition path for deliverymen.

#### Scenario: Rider mark uses shared mark_delivery path

- **WHEN** a verified deliveryman marks an eligible zone `scheduled` delivery as `delivered` and the customer wallet can pay the meal
- **THEN** the delivery becomes `delivered`, exactly one meal-payment debit is created for that delivery under the same rules as auto-delivery, and the customer notify path runs for a real transition

#### Scenario: Cron after rider does not double charge

- **WHEN** a deliveryman has already marked a delivery `delivered` and charged the wallet, and auto-delivery later runs for the same meal period
- **THEN** auto-delivery does not create a second debit for that delivery

### Requirement: Deliveryman mark-delivered applies auto-delivery eligibility gates

Before completing mark-delivered, the system MUST reject a deliveryman request when the delivery’s customer is meal-service blocked for low balance (`CustomerProfile.meal_service_blocked_low_balance=true`), matching auto-delivery candidate exclusion. The rejection MUST leave the delivery status unchanged, MUST NOT debit the wallet, and MUST return a client-safe error with a stable machine-readable error code. Zone scoping MUST still apply: deliveries outside the rider’s assigned zone remain forbidden independently of meal-stop state.

#### Scenario: Rider cannot mark low-balance meal-stop customer

- **WHEN** a verified deliveryman posts mark `delivered` for a zone delivery whose customer has `meal_service_blocked_low_balance=true`
- **THEN** the request is rejected, the delivery remains `scheduled` (or its prior status), and no meal-payment debit is created

#### Scenario: Unblocked eligible rider mark still succeeds

- **WHEN** the same rider marks a zone `scheduled` delivery for a customer who is not meal-stop blocked and whose wallet can pay
- **THEN** mark-delivered succeeds through the shared completion pipeline

#### Scenario: Out-of-zone remains forbidden even if unblocked

- **WHEN** a deliveryman attempts to mark a delivery whose customer location is outside the rider’s assigned zone
- **THEN** the request is forbidden regardless of meal-stop block state

### Requirement: Admin mark-delivered remains the override for blocked customers

The system MUST continue to allow verified admin/operator mark-delivered for meal-stop blocked customers under existing meal payment rules. Deliveryman field mark-delivered MUST NOT receive that override.

#### Scenario: Admin can mark blocked customer while rider cannot

- **WHEN** a customer is meal-stop blocked with a `scheduled` delivery, an admin marks that delivery delivered successfully under meal payment rules, and a deliveryman attempts the same mark on an equivalent blocked slot
- **THEN** the admin path may complete (subject to wallet rules) while the deliveryman path is rejected by the eligibility gate
