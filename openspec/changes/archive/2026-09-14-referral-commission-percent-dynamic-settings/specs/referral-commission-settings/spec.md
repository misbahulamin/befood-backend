## ADDED Requirements

### Requirement: Database-backed referral commission percentage

The system SHALL persist the active referral commission percentage in a singleton `ReferralProgramSettings` row (`pk=1`) with a decimal `commission_percent` field. The field MUST accept values from `0` through `100` inclusive with at most two decimal places. Creating the singleton MUST seed from Django setting `REFERRAL_COMMISSION_PERCENT` when available, otherwise default to `5.00`. Changing this setting MUST NOT modify existing `ReferralCommission` rows, customer wallet balances, or Admin Wallet transactions.

#### Scenario: Singleton seeds from env default

- **WHEN** the singleton settings row is created for the first time and `REFERRAL_COMMISSION_PERCENT` is unset or `"5"`
- **THEN** the stored `commission_percent` is `5.00`

#### Scenario: Settings change leaves history untouched

- **WHEN** an admin updates `commission_percent` from `5.00` to `10.00` and prior `success` commission rows exist
- **THEN** those prior rows keep their original `commission_percent` and `commission_amount` values and no wallet ledger rows are rewritten

### Requirement: Accrual uses live settings percent

The system SHALL resolve the commission rate for new accrual calculations through `commission_percent()` by reading `ReferralProgramSettings` (not by relying solely on a process-static env constant after the singleton exists). Accrual MUST snapshot the resolved percent onto the `ReferralCommission` row at write/upgrade time. Amount calculation MUST remain `ROUND_HALF_UP` to two decimal places of `charged_amount * percent / 100` inside the existing atomic accrual transaction.

#### Scenario: New delivery uses updated percent

- **WHEN** settings `commission_percent` is `10.00` and a referred delivery accrues successfully
- **THEN** the new commission row stores `commission_percent` of `10.00` and amount based on 10% of charged amount

#### Scenario: Percent read inside accrual transaction

- **WHEN** accrual runs for a delivery
- **THEN** the percent used for amount calculation is the live settings value read for that accrual attempt and wallet debit/credit occur in the same atomic transaction as today

### Requirement: Verified-admin referral settings API

The system SHALL expose verified-admin endpoints:

- `GET /api/v1/web/referrals/settings/`
- `PATCH /api/v1/web/referrals/settings/`

Both MUST require `IsVerifiedAdmin`. GET MUST return at least `referral_commission_percent` and `updated_at`. PATCH MUST accept partial updates of `referral_commission_percent`, validate the range, persist the singleton, and return the updated resource. Unauthenticated or non-verified-admin callers MUST receive `401`/`403` as appropriate. Invalid values (below `0`, above `100`, or more than two decimal places) MUST be rejected with a validation error and MUST NOT change the stored value.

#### Scenario: Admin retrieves current percent

- **WHEN** a verified admin calls `GET /api/v1/web/referrals/settings/`
- **THEN** the response is `200` with the current `referral_commission_percent`

#### Scenario: Admin updates percent

- **WHEN** a verified admin `PATCH`es `{ "referral_commission_percent": "10.00" }`
- **THEN** the singleton is updated and the response is `200` with `referral_commission_percent` of `"10.00"`

#### Scenario: Invalid percent rejected

- **WHEN** a verified admin `PATCH`es `{ "referral_commission_percent": "150" }` or a negative value
- **THEN** the API rejects the request with a validation error and the stored percent is unchanged

#### Scenario: Non-admin denied

- **WHEN** a customer or unverified admin calls GET or PATCH on the settings endpoint
- **THEN** the request is denied (`401` or `403`)
