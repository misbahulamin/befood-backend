## ADDED Requirements

### Requirement: Admin settings page Referral section

The Admin Frontend Settings page at `/admin/settings` SHALL include a Referral Settings section that displays and edits the live referral commission percentage. The section MUST load data from `GET /api/v1/web/referrals/settings/` and save via `PATCH /api/v1/web/referrals/settings/` using the authenticated verified-admin session and `X-Client-Type: web`. The UI MUST present the current percentage, an editable control, and a save action with clear success and error feedback.

#### Scenario: Load current percentage

- **WHEN** a verified admin opens `/admin/settings` and the Referral Settings section mounts
- **THEN** the UI requests `GET /api/v1/web/referrals/settings/` and shows the returned `referral_commission_percent`

#### Scenario: Save updated percentage

- **WHEN** the admin enters a valid percentage and saves
- **THEN** the UI sends `PATCH /api/v1/web/referrals/settings/` with `referral_commission_percent` and shows a success state on `200`

### Requirement: Client-side validation and permission UX

The Referral Settings UI MUST prevent submitting values outside `0`–`100` (inclusive) before calling the API, and MUST still surface backend validation errors if the API rejects the payload. The settings route MUST remain restricted to verified admins; non-admin users MUST NOT be able to update the percentage through this page.

#### Scenario: Client blocks out-of-range input

- **WHEN** the admin enters `-5` or `150` and attempts to save
- **THEN** the UI blocks or shows a validation message and does not call PATCH (or does not treat a rejected call as success)

#### Scenario: Backend error shown

- **WHEN** PATCH returns a validation or permission error
- **THEN** the UI shows an error message and retains the last known good displayed value until a successful reload/save
