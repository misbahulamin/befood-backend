## MODIFIED Requirements

### Requirement: All resume entry points share cutoff skip behavior

Admin recharge approval, successful withdraw reject after reservation release, wallet credit resume hooks, and wallet-threshold cron resume MUST apply the same post-resume cutoff-skip rules whenever a low-balance meal-stop block is cleared due to balance recovery. Manual admin actions that clear the same block, if present, MUST be inspected and aligned so they cannot reintroduce past-cutoff cook counts without the skip step.

#### Scenario: Cron resume after cutoff also skips

- **WHEN** the wallet-threshold cron clears a low-balance block after lunch cutoff because balance recovered
- **THEN** today’s past-cutoff lunch slot is system-skipped the same way as after recharge approval

#### Scenario: Withdraw reject resume after cutoff also skips

- **WHEN** a verified admin rejects a pending withdraw that clears low-balance meal-stop after lunch cutoff because restored balance meets `meal_stop_threshold`
- **THEN** today’s past-cutoff lunch slot is system-skipped the same way as after recharge approval
