# Order Wallet Minimum Balance Settings

## Purpose
Define the configurable wallet balance threshold required before a customer may create a meal package order.

## Requirements

### Requirement: Order wallet settings singleton

The system SHALL store a single order-wallet settings record with:

- `min_wallet_balance_to_order` (decimal monetary amount in BDT, default `500.00`, must be greater than or equal to `0`)

Missing settings MUST be created with these defaults on first load.

#### Scenario: Defaults applied on first load

- **WHEN** a verified admin loads order wallet settings and no row exists yet
- **THEN** the response uses `min_wallet_balance_to_order` of `500.00`

### Requirement: Verified admin can view and update the minimum

The system SHALL allow a verified admin to retrieve and partially update order wallet settings. Non-admin clients MUST NOT update the settings. Negative amounts and amounts with more than two decimal places MUST be rejected. Updated values MUST apply to subsequent order eligibility checks.

#### Scenario: Admin raises the minimum

- **WHEN** a verified admin patches `min_wallet_balance_to_order` to `600.00`
- **THEN** subsequent order creates require wallet balance ≥ `600.00`

#### Scenario: Admin lowers the minimum

- **WHEN** a verified admin patches `min_wallet_balance_to_order` to `300.00` and a customer with balance `300.00` and no month lock creates an order
- **THEN** the system creates the order successfully

#### Scenario: Non-admin cannot update settings

- **WHEN** an unauthenticated or non-admin client attempts to update order wallet settings
- **THEN** the system rejects the request with `401` or `403`

#### Scenario: Negative minimum rejected

- **WHEN** an admin submits `min_wallet_balance_to_order` of `-1.00`
- **THEN** the system returns a validation error on that field and does not change the stored value

### Requirement: Customers can discover the required minimum

The system SHALL expose the current `min_wallet_balance_to_order` to authenticated verified customers on a read path suitable for the order/wallet UX (for example wallet detail), without allowing customers to modify it.

#### Scenario: Customer reads the configured minimum

- **WHEN** an authenticated verified customer requests their wallet (or the designated read endpoint)
- **THEN** the response includes the current `min_wallet_balance_to_order` value used for order eligibility
