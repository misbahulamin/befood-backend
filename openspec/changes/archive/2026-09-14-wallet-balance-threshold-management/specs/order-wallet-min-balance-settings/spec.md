## MODIFIED Requirements

### Requirement: Order wallet settings singleton

The system SHALL store a single order-wallet settings record with:

- `min_wallet_balance_to_order` (decimal monetary amount in BDT, default `500.00`, must be greater than or equal to `0`) — subscription minimum balance gate
- `low_balance_reminder_threshold` (decimal monetary amount in BDT, default `300.00`, must be greater than or equal to `0`)
- `meal_stop_threshold` (decimal monetary amount in BDT, default `200.00`, must be greater than or equal to `0`)

Missing settings MUST be created with these defaults on first load. Stored values MUST satisfy:

`min_wallet_balance_to_order > low_balance_reminder_threshold > meal_stop_threshold ≥ 0`

#### Scenario: Defaults applied on first load

- **WHEN** a verified admin loads order wallet settings and no row exists yet
- **THEN** the response uses `min_wallet_balance_to_order` of `500.00`, `low_balance_reminder_threshold` of `300.00`, and `meal_stop_threshold` of `200.00`

### Requirement: Verified admin can view and update the minimum

The system SHALL allow a verified admin to retrieve and partially update order wallet settings. Non-admin clients MUST NOT update the settings. Negative amounts and amounts with more than two decimal places MUST be rejected. Updated values MUST apply to subsequent subscription eligibility checks and wallet-threshold automation. Partial updates MUST be validated against the merged result with currently stored values so threshold ordering cannot be broken. Cross-field ordering violations MUST be rejected without changing stored settings.

#### Scenario: Admin raises the minimum

- **WHEN** a verified admin patches `min_wallet_balance_to_order` to `600.00` while reminder and meal-stop remain ordered below it
- **THEN** subsequent subscription creates require wallet balance ≥ `600.00`

#### Scenario: Admin lowers the minimum

- **WHEN** a verified admin patches `min_wallet_balance_to_order` to `300.00` only if the merged thresholds still satisfy strict ordering, and a customer with balance `300.00` creates a subscription
- **THEN** the system creates the subscription successfully when ordering remains valid

#### Scenario: Non-admin cannot update settings

- **WHEN** an unauthenticated or non-admin client attempts to update order wallet settings
- **THEN** the system rejects the request with `401` or `403`

#### Scenario: Negative minimum rejected

- **WHEN** an admin submits `min_wallet_balance_to_order` of `-1.00`
- **THEN** the system returns a validation error on that field and does not change the stored value

#### Scenario: Threshold ordering conflict rejected

- **WHEN** a verified admin submits values where `low_balance_reminder_threshold` is greater than or equal to `min_wallet_balance_to_order`, or `meal_stop_threshold` is greater than or equal to `low_balance_reminder_threshold`
- **THEN** the system returns a validation error and does not change the stored settings

#### Scenario: Admin updates reminder and meal-stop thresholds

- **WHEN** a verified admin patches `low_balance_reminder_threshold` to `300.00` and `meal_stop_threshold` to `200.00` with `min_wallet_balance_to_order` at `500.00`
- **THEN** the stored settings reflect those values and subsequent cron evaluations use them

## ADDED Requirements

### Requirement: Customers can discover reminder and meal-stop thresholds

The system SHALL expose the current `low_balance_reminder_threshold` and `meal_stop_threshold` to authenticated verified customers on the wallet (or designated) read path, without allowing customers to modify them.

#### Scenario: Customer reads all configured thresholds

- **WHEN** an authenticated verified customer requests their wallet
- **THEN** the response includes `min_wallet_balance_to_order`, `low_balance_reminder_threshold`, and `meal_stop_threshold`
