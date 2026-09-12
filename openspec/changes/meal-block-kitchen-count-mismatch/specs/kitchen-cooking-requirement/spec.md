## ADDED Requirements

### Requirement: Post-charge meal-stop exclusion appears in kitchen cooking counts without waiting for evening cron

The system SHALL continue to exclude customers with `CustomerProfile.meal_service_blocked_low_balance=true` from Kitchen Today cooking headcount and ingredient scaling (`final_cooking_count` and related demand buckets that already omit low-balance blocked customers). When a successful meal-payment debit causes immediate meal-stop blocking under `post-meal-charge-meal-stop`, a subsequent kitchen today-meal-requirement (or today-order-details) request for an affected dinner/lunch slot MUST omit that customer from cook counts without requiring the 20:00 Asia/Dhaka wallet-threshold cron to have run. Kitchen MUST NOT depend on a separate cache invalidation step; live querysets over the block flag are sufficient. This change MUST NOT require kitchen to recompute exclusion from live `Wallet.balance < meal_stop_threshold` in place of the block flag.

#### Scenario: After lunch charge block, dinner kitchen count drops before 20:00

- **WHEN** lunch auto-delivery successfully charges a customer so post-debit balance is below `meal_stop_threshold`, meal-stop block is applied immediately, and a verified admin then requests kitchen today-meal-requirement for today’s dinner before 20:00 Asia/Dhaka
- **THEN** that customer is not included in `final_cooking_count` for dinner

#### Scenario: Kitchen still uses block flag not raw balance for cook exclusion

- **WHEN** a customer has spendable balance below `meal_stop_threshold` but `meal_service_blocked_low_balance` is still `false`
- **THEN** kitchen cooking exclusion for that customer remains governed by the block flag (and other existing live-delivery/skip rules), not by a new live-balance cook formula introduced in this change
