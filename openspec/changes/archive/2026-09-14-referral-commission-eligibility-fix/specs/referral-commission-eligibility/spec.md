## ADDED Requirements

### Requirement: Commission requires dual active subscriptions and co-consumption
The system SHALL credit referral commission for a referred customer’s meal only when all of the following are true at accrual evaluation time: (1) a referral relationship exists for the referred customer, (2) the referrer has an active meal subscription, (3) the referred customer has an active meal subscription, (4) the referred `OrderDelivery` is `delivered` and charged, and (5) the referrer has consumed the same meal, meaning an `OrderDelivery` for the same `service_date` and the same `meal_period` with status `delivered`. The referrer matching delivery MUST NOT be required to have `payment_status=charged`. If any condition fails, the system MUST NOT create a successful money movement for that referred delivery.

#### Scenario: Both consume same lunch same day
- **WHEN** referrer and referred both have active subscriptions, both have lunch `delivered` on `2026-09-10`, and the referred lunch delivery is charged
- **THEN** the system records a successful referral commission for that referred delivery

#### Scenario: Referrer delivered without charge still qualifies
- **WHEN** the referred lunch is delivered and charged and the referrer’s matching lunch is `delivered` but not charged
- **THEN** the system still treats the referrer meal as consumed for eligibility and may credit commission if other gates pass

#### Scenario: Referrer meal off same day
- **WHEN** the referred customer’s lunch on `2026-09-10` is delivered and charged but the referrer has lunch OFF (no matching delivered lunch that day)
- **THEN** the system does not credit commission success for that delivery and records a non-success outcome with reason `REFERRER_MEAL_NOT_CONSUMED`

#### Scenario: Different meal period same day
- **WHEN** the referred customer’s lunch is delivered and charged on a date where the referrer only has a delivered breakfast
- **THEN** the system does not credit commission success and records `REFERRER_MEAL_NOT_CONSUMED`

#### Scenario: Same meal different dates
- **WHEN** the referred customer’s lunch is delivered and charged today but the referrer’s matching lunch was delivered only on a prior date
- **THEN** the system does not credit commission success and records `REFERRER_MEAL_NOT_CONSUMED`

#### Scenario: Inactive subscription still blocks
- **WHEN** co-consumption would match but the referrer or referred lacks an active subscription
- **THEN** the system does not credit commission success and records the existing inactive skip reason (`REFERRER_INACTIVE` or `REFERRED_INACTIVE`)

### Requirement: Accrual upgrades skipped rows in place when the second party completes the matching meal
The system SHALL not permanently lose a fair commission solely because the referred meal completed before the referrer’s matching meal. After a referred delivery is charged, if the referrer later completes a matching delivered meal for the same `service_date` and `meal_period`, OR a reconcile job runs while eligibility is satisfied, the system MUST re-evaluate eligibility and MUST upgrade the existing retryable meal-mismatch `skipped` `ReferralCommission` row for that referred delivery to `success` in place. The system MUST NOT create a second non-manual success commission row for the same referred `OrderDelivery`. The system MUST still enforce at most one successful non-manual commission money movement per referred `OrderDelivery`.

#### Scenario: Referred delivers first then referrer matches later
- **WHEN** the referred lunch is charged first (referrer lunch not yet delivered) creating a `skipped` / `REFERRER_MEAL_NOT_CONSUMED` row, and later the same day the referrer’s lunch is marked delivered
- **THEN** the system upgrades that same commission row to `success` and credits at most one successful money movement

#### Scenario: Idempotent after success
- **WHEN** accrual or reconcile runs again after a successful co-consumption commission for a delivery
- **THEN** no second Admin Wallet debit or referrer commission credit occurs

### Requirement: Machine-readable skip reason for missing referrer meal
The system SHALL use status reason `REFERRER_MEAL_NOT_CONSUMED` when accrual is blocked specifically because the referrer lacks a matching delivered meal for the referred delivery’s `service_date` and `meal_period`. Customer and admin commission list APIs that already expose `status_reason` MUST return this value for such outcomes.

#### Scenario: Commission list shows meal mismatch reason
- **WHEN** a commission attempt is skipped because the referrer did not consume the same meal
- **THEN** `GET` commission list payloads include `status_reason` equal to `REFERRER_MEAL_NOT_CONSUMED`

### Requirement: Reconcile uses co-consumption eligibility and supports dry-run
The referral commission reconcile command SHALL apply the same dual-subscription and same-day same-meal co-consumption rules when backfilling missing accruals or retrying eligible outcomes, including in-place upgrade of retryable `REFERRER_MEAL_NOT_CONSUMED` skips. It MUST NOT create a successful commission for a referred delivered meal when the referrer did not consume the matching meal. The command MUST support a `--dry-run` mode that reports intended creates/upgrades/retries without performing wallet or commission money writes.

#### Scenario: Reconcile does not pay meal-off referrer
- **WHEN** reconcile finds a charged referred delivery without success commission and the referrer has no matching delivered meal
- **THEN** reconcile does not create a successful commission credit for that delivery

#### Scenario: Dry-run performs no money movement
- **WHEN** reconcile is invoked with `--dry-run` for deliveries that would otherwise accrue or upgrade
- **THEN** the command reports the planned actions and does not debit Admin Wallet, credit commission balance, or persist success money movements

### Requirement: Historical successful commissions are not auto-clawed back
Deploying co-consumption eligibility MUST NOT automatically reverse existing `success` commissions that were created under the previous looser rule. Any clawback MUST use the existing admin reverse (or an explicitly approved one-off ops process).

#### Scenario: Pre-fix success remains until manual reverse
- **WHEN** the eligibility fix is deployed and a prior `success` commission would fail the new co-consumption rule
- **THEN** that commission remains `success` until an authorized reverse or approved ops process changes it

### Requirement: Co-consumption lookup path is index-reviewed
Implementation SHALL review `OrderDelivery` indexes for the chosen referrer meal lookup (preferred: subscription + `service_date` + `meal_period`, asserting `status=delivered`). If the chosen query path is not covered adequately by existing indexes/constraints, the system MUST add a supporting index before relying on high-volume dual-trigger or reconcile scans in production.

#### Scenario: Index review recorded before production dual-trigger volume
- **WHEN** co-consumption eligibility queries are implemented
- **THEN** engineers confirm existing unique `(subscription, service_date, meal_period)` / indexes suffice or add a measured supporting index
