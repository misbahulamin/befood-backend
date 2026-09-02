## ADDED Requirements

### Requirement: Admin Settings exposes three wallet thresholds

The Admin Frontend Settings page SHALL allow a verified admin to view and update:

- Minimum subscription wallet balance (`min_wallet_balance_to_order`)
- Low balance reminder threshold (`low_balance_reminder_threshold`)
- Meal stop threshold (`meal_stop_threshold`)

using the existing order-wallet-settings API. The UI MUST present amounts in BDT and show clear labels describing each threshold’s purpose.

#### Scenario: Admin saves valid ordered thresholds

- **WHEN** a verified admin enters subscription `500`, reminder `300`, and meal-stop `200` and saves
- **THEN** the client sends a PATCH with those fields and shows the updated values after success

### Requirement: Client-side ordering validation

Before submit, the Admin Frontend MUST prevent saves that violate  
`subscription minimum > reminder threshold > meal stop threshold ≥ 0`,  
and surface a clear validation message. Server validation remains authoritative.

#### Scenario: Invalid order blocked in UI

- **WHEN** a verified admin sets subscription minimum to `200` and reminder threshold to `500`
- **THEN** the UI blocks submit and explains that subscription minimum must be greater than the reminder threshold

### Requirement: Permission-gated settings

Only verified admin sessions MAY load or mutate these settings in the admin panel. Unauthenticated or non-admin users MUST NOT reach a working edit form for these fields.

#### Scenario: Non-admin cannot edit thresholds

- **WHEN** a non-admin user navigates to admin settings
- **THEN** they cannot successfully update wallet threshold settings
