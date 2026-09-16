## ADDED Requirements

### Requirement: Resume clears financial block without permanent preference changes

When spendable wallet balance recovers to at least the live `meal_stop_threshold` and the customer has `meal_service_blocked_low_balance=true`, the system SHALL clear that block (`true` means blocked; `false` means not blocked) so the customer is financially eligible for future meal service. Clearing the block MUST NOT permanently turn off the customer’s lunch/dinner meal preference or subscription meal defaults.

#### Scenario: Balance recovers and block clears

- **WHEN** a low-balance-blocked customer’s spendable balance becomes `>= meal_stop_threshold` via approved recharge (or equivalent credit/cron resume path)
- **THEN** `meal_service_blocked_low_balance` becomes `false` and permanent meal preferences remain unchanged

#### Scenario: Manual meal-off is not forced back on

- **WHEN** the customer already has today’s dinner `skipped` with customer meal-off and then recharges past threshold after lunch cutoff but before dinner cutoff
- **THEN** the system MUST NOT convert that customer dinner skip back to `scheduled`

### Requirement: Past-cutoff meals stay skipped on the service date after resume

On successful low-balance resume, the system MUST evaluate the current business date and local time using `MealOffSettings` timezone and configured `lunch_off_time` / `dinner_off_time` (MUST NOT hardcode cutoff clock times or the meal-stop amount). For each of today’s meal periods whose cutoff has already passed (`business now` strictly after that period’s deadline), the customer’s still-cookable delivery for that `(service_date, meal_period)` MUST be marked ineligible for cooking via existing delivery skip semantics (`status=skipped`, system skip source, stable audit note). Periods whose cutoff has not passed MUST remain governed by the customer’s existing slot state.

#### Scenario: Recharge before lunch cutoff restores lunch eligibility state

- **WHEN** lunch cutoff is `02:00` Asia/Dhaka, the customer is low-balance blocked with lunch normally `scheduled`, and recharge resumes the customer at `01:30`
- **THEN** the financial block is cleared and today’s lunch remains `scheduled` (eligible for kitchen if otherwise ON)

#### Scenario: Recharge after lunch cutoff skips today’s lunch only

- **WHEN** lunch cutoff is `02:00` Asia/Dhaka and the customer resumes at `08:00` while lunch was still `scheduled` under the block
- **THEN** the financial block is cleared, today’s lunch is system-skipped for that service date, and tomorrow’s lunch is not auto-skipped by this resume

#### Scenario: Lunch cutoff passed, dinner cutoff not passed

- **WHEN** business time is `08:00`, lunch cutoff already passed, dinner cutoff is still in the future, and the customer resumes with dinner `scheduled`
- **THEN** today’s lunch is system-skipped and today’s dinner remains eligible according to its existing non-skipped state

#### Scenario: Both cutoffs passed

- **WHEN** business time is after both lunch and dinner cutoffs and the customer resumes
- **THEN** today’s lunch and dinner cookable slots are system-skipped and the next eligible future meal follows normal rules

#### Scenario: Resume exactly at cutoff remains eligible

- **WHEN** business time equals the lunch deadline exactly and the customer resumes with lunch `scheduled`
- **THEN** today’s lunch is NOT treated as past-cutoff and remains eligible under existing preference/state

#### Scenario: Repeated resumes are idempotent

- **WHEN** multiple payment approvals or resume calls run for the same customer after cutoff
- **THEN** the system MUST NOT create duplicate delivery rows and MUST leave an already system-skipped slot unchanged (no conflicting status thrash)

### Requirement: All resume entry points share cutoff skip behavior

Admin recharge approval, wallet credit resume hooks, and wallet-threshold cron resume MUST apply the same post-resume cutoff-skip rules whenever a low-balance meal-stop block is cleared due to balance recovery. Manual admin actions that clear the same block, if present, MUST be inspected and aligned so they cannot reintroduce past-cutoff cook counts without the skip step.

#### Scenario: Cron resume after cutoff also skips

- **WHEN** the wallet-threshold cron clears a low-balance block after lunch cutoff because balance recovered
- **THEN** today’s past-cutoff lunch slot is system-skipped the same way as after recharge approval
