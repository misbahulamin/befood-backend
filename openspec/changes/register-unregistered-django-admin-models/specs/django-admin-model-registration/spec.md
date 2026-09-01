## ADDED Requirements

### Requirement: DeviceToken visible in Django Admin

The system SHALL register `DeviceToken` in Django Admin under `user_management` with list display showing `user`, `platform`, `device_name`, `is_active`, `last_used_at`, and `created_at`.

#### Scenario: Admin lists device tokens

- **WHEN** a staff user with Django Admin access opens the DeviceToken changelist
- **THEN** the system displays paginated device token rows with user email searchable via `user__email` and token value searchable via `token`

#### Scenario: Admin filters active tokens

- **WHEN** a staff user filters the DeviceToken changelist by `is_active=True` and `platform=android`
- **THEN** the system shows only matching active Android tokens

### Requirement: StaffProfile visible in Django Admin

The system SHALL register `StaffProfile` in Django Admin with list display showing `user`, `role`, and `outlet_id`, and `user` as an autocomplete field.

#### Scenario: Admin searches staff profiles

- **WHEN** a staff user searches the StaffProfile changelist by user email
- **THEN** the system returns matching staff profile rows

### Requirement: UserActivityLog read-only in Django Admin

The system SHALL register `UserActivityLog` in Django Admin as read-only: no add, change, or delete permissions; list display showing `user`, `action`, `ip_address`, and `timestamp`; ordered by newest first.

#### Scenario: Admin views activity log

- **WHEN** a staff user opens the UserActivityLog changelist
- **THEN** the system displays audit entries ordered by `-timestamp` with search on `user__email` and `action`

#### Scenario: Admin cannot mutate activity log

- **WHEN** a staff user attempts to add, edit, or delete a UserActivityLog entry via Django Admin
- **THEN** the system denies the operation

### Requirement: Admin registration follows existing patterns

New ModelAdmin classes SHALL follow conventions established in `user_management/admin.py` (autocomplete for FKs to `User`, readonly timestamps where auto-managed, consistent search_fields).

#### Scenario: DeviceToken admin uses autocomplete for user

- **WHEN** a staff user opens a DeviceToken add/change form
- **THEN** the `user` field is rendered as an autocomplete widget linked to the User admin
