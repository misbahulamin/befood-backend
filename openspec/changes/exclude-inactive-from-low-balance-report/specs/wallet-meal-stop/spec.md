# Spec Delta

## MODIFIED Requirements

### Requirement: Notify customer on meal stop

When meal service becomes blocked for low balance for a customer with an active meal subscription, the system SHALL notify the customer via push (when tokens exist) and branded email that meal service has stopped until they recharge. Customers without an active meal subscription MUST NOT receive meal-stop low-balance notifications from the wallet-threshold cron path.

#### Scenario: Stop notification on transition

- **WHEN** an active subscriber transitions from unblocked to blocked because balance is below `meal_stop_threshold`
- **THEN** the system sends a meal-stop push and email explaining that recharging is required to resume meals

#### Scenario: Non-active customer not notified on cron

- **WHEN** the wallet-threshold cron encounters a cancelled or never-subscribed customer whose balance is below `meal_stop_threshold`
- **THEN** the system does not send meal-stop push or email for that customer via the cron path

## ADDED Requirements

### Requirement: Clear low-balance block when subscription is cancelled

When a meal subscription is cancelled, the system SHALL clear any existing low-balance meal-service block on that customer so the customer is no longer treated as low-balance blocked solely due to the prior subscription period.

#### Scenario: Cancel clears leftover meal-stop flag

- **WHEN** an active subscriber with `meal_service_blocked_low_balance` true cancels their meal subscription
- **THEN** the system clears the meal-service block flag as part of cancel handling and the customer is no longer counted as low-balance blocked for threshold reporting
