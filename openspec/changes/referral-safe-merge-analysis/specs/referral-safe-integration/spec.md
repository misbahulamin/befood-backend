## ADDED Requirements

### Requirement: Integration branch is based on production main
The system SHALL integrate unfinished referral work only onto a branch created from up-to-date `origin/main` (including merged production-hotfix commits). Local stale `main` MUST NOT be treated as the production baseline.

#### Scenario: Baseline is origin/main tip
- **WHEN** an integration branch is created for referral porting
- **THEN** it is based on current `origin/main` after fetch, not on stale local `main` alone

### Requirement: Wallet migration graph preserves production 0004
The integration MUST keep production’s `wallet.0004_live_status_provider_recharge_ref_unique` migration. Dual-bucket wallet schema changes MUST be introduced as a later migration that depends on that `0004`, never as a competing `0004` leaf.

#### Scenario: No duplicate wallet 0004
- **WHEN** migrations are listed for the `wallet` app on the integration branch
- **THEN** exactly one `0004_*` migration exists and it is the live-status provider-ref uniqueness migration from production

#### Scenario: Dual bucket follows live-status migration
- **WHEN** dual-bucket balance columns are introduced
- **THEN** their migration depends on `0004_live_status_provider_recharge_ref_unique` (or equivalent renumbered successor chain rooted after it)

### Requirement: Production wallet hotfix behaviors are retained
After integrating dual-bucket and referral commission, the system MUST retain production-hotfix wallet behaviors: provider recharge external refs are unique among live (`pending`/`completed`) rows, and approving a customer recharge MUST still evaluate meal-service auto-resume for the admin approve response.

#### Scenario: Failed recharge does not block ref reuse
- **WHEN** a provider recharge with external ref `X` is `failed` or `cancelled` and a new live recharge with the same method and ref `X` is submitted
- **THEN** the system allows the new live recharge (subject to other validation) and does not treat failed/cancelled rows as owning the unique constraint

#### Scenario: Approve still reports meal service resume
- **WHEN** an admin approves a pending recharge that clears a low-balance meal stop
- **THEN** the approve path still attaches/exposes `meal_service_restored` consistent with production-hotfix behavior

### Requirement: Conflict resolution prefers composition over either side alone
For files changed on both `origin/main` and `unfinished-features` (`wallet/models.py`, `wallet/services/funding.py`, `wallet/api/serializers.py`, `core/urls.py`, `user_management/models.py`, wallet docs), the integration MUST combine behaviors rather than taking a single side wholesale. `db.sqlite3` MUST NOT be committed.

#### Scenario: Funding file contains both bucket and hotfix logic
- **WHEN** `wallet/services/funding.py` is finalized on the integration branch
- **THEN** it includes recharge-bucket withdraw/approve/reject accounting and live-status provider-ref checks and meal-service resume on approve

#### Scenario: SQLite is excluded
- **WHEN** integration commits are prepared
- **THEN** `db.sqlite3` is not staged or committed
