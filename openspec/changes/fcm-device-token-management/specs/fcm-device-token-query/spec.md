## ADDED Requirements

### Requirement: get_user_device_tokens returns active tokens for one user

The system SHALL provide a service function `get_user_device_tokens(user)` in `notifications/services/device_service.py` that returns only active, non-empty token strings for the given user. The function MUST use `values_list("token", flat=True)` (or equivalent) and MUST NOT load full `User` objects or unnecessary model fields.

#### Scenario: Active tokens returned

- **WHEN** a user has two active tokens and one inactive token
- **THEN** `get_user_device_tokens(user)` returns exactly the two active token strings

#### Scenario: Empty tokens excluded

- **WHEN** a user has an active row with an empty or whitespace-only token (should not occur after validation)
- **THEN** the function excludes that token from results

#### Scenario: No N+1 on user lookup

- **WHEN** `get_user_device_tokens(user)` is called
- **THEN** the query MUST NOT perform additional queries to load the User object beyond what the caller already has

### Requirement: get_all_active_device_tokens returns all active tokens

The system SHALL provide a service function `get_all_active_device_tokens()` that returns all active, non-empty token strings across all users, optimized for broadcast send paths. The function MUST use `values_list("token", flat=True)` and MUST NOT prefetch or select related User records.

#### Scenario: Broadcast query returns all active tokens

- **WHEN** the database has 5 active tokens across 3 users and 2 inactive tokens
- **THEN** `get_all_active_device_tokens()` returns exactly 5 token strings

#### Scenario: Queryset does not fetch unnecessary fields

- **WHEN** `get_all_active_device_tokens()` executes
- **THEN** the database query selects only the `token` column (via values_list)

### Requirement: Device management is decoupled from FCM sending

Token storage and query services MUST live in `notifications/services/device_service.py`. Firebase message sending MUST be stubbed in `notifications/services/fcm_service.py` without importing or initializing Firebase credentials in this change. Future send logic MUST call `device_service` query helpers rather than querying `DeviceToken` directly from send code.

#### Scenario: fcm_service does not initialize Firebase

- **WHEN** the application starts with this change deployed
- **THEN** no Firebase Admin SDK initialization occurs and no credentials are required

#### Scenario: fcm_service stub exists for future integration

- **WHEN** a developer inspects `notifications/services/fcm_service.py`
- **THEN** placeholder functions for send operations exist and are documented as not yet implemented

### Requirement: register_device_token encapsulates all write logic

All create/update/ownership-transfer logic for device tokens MUST reside in `register_device_token()` within `device_service.py`. API views MUST NOT contain business logic beyond calling the service and mapping exceptions to HTTP responses. Write operations MUST run inside `transaction.atomic()`.

#### Scenario: Concurrent register for same token is safe

- **WHEN** two concurrent register requests arrive with the same token for the same user
- **THEN** exactly one row exists after both complete and no integrity error propagates to the client
