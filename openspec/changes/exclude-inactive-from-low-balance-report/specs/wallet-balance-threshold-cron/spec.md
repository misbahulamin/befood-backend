# Spec Delta

## MODIFIED Requirements

### Requirement: Cron evaluates active verified subscribers

Each cron execution SHALL load configured thresholds and evaluate only verified customers who currently have an active meal subscription. The run MUST apply meal-stop then reminder priority for those customers and invoke the admin low-balance summary for the run. Customers with a cancelled subscription, or with no meal subscription, MUST NOT be evaluated for meal-stop notify, low-balance reminder, or admin-summary inclusion solely because a leftover low-balance meal-service block flag remains set.

#### Scenario: Combined case handling in one run

- **WHEN** the cron runs and one active subscriber is below meal-stop and another active subscriber is only below reminder
- **THEN** the first is meal-stopped (and notified per meal-stop rules), the second receives a reminder (subject to daily idempotency), and both appear in the admin summary as applicable

#### Scenario: Cancelled subscriber excluded from threshold cohort

- **WHEN** the cron runs for a verified customer whose meal subscription is cancelled (or who has never subscribed), even if `meal_service_blocked_low_balance` is still true and wallet balance is below thresholds
- **THEN** the system does not send that customer low-balance or meal-stop notifications for the cron path and does not include them in the admin low-balance summary for that run
