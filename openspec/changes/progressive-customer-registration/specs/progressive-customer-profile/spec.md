## ADDED Requirements

### Requirement: Authenticated partial profile update with immediate persistence
The system SHALL allow a verified, authenticated customer to update onboarding profile fields incrementally via the existing `PATCH /user_management/customer/profile/` endpoint (or equivalent project convention). Each accepted PATCH MUST validate only submitted fields, persist them immediately to the database, and return the updated profile representation. Submitted steps MUST NOT be held in session or pending state server-side.

#### Scenario: Name fields saved independently
- **WHEN** an authenticated customer PATCHes `{ "first_name": "John", "last_name": "Doe" }`
- **THEN** the system updates `User.first_name` and `User.last_name`, returns success, and leaves other fields unchanged

#### Scenario: Phone saved in a separate step
- **WHEN** an authenticated customer later PATCHes `{ "phone": "01712345678" }`
- **THEN** the system validates and stores the phone on `CustomerProfile`, returns success, and preserves previously saved name fields

#### Scenario: Demographics saved independently
- **WHEN** an authenticated customer PATCHes `{ "gender": "male", "is_bachelor": true }`
- **THEN** the system stores valid enum/boolean values and preserves unrelated existing profile data

#### Scenario: Occupation saved independently
- **WHEN** an authenticated customer PATCHes `{ "occupation": "student" }`
- **THEN** the system accepts only valid `CustomerProfile.Occupation` choices and persists the value

### Requirement: Writable onboarding fields use strict allow-list
The profile update serializer MUST allow writes only to onboarding-safe fields: `first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`, `gender`, plus existing extended profile fields already supported on PATCH (`birth_date`, emergency contacts, food preferences, etc.). The endpoint MUST NOT allow clients to modify privileged fields including `is_email_verified`, `email_verified_at`, `profile_completed`, `profile_completion_percentage`, `user.is_active`, groups/roles, wallet balances, or internal identifiers.

#### Scenario: Privileged field mass assignment blocked
- **WHEN** an authenticated customer PATCHes `{ "is_email_verified": true, "profile_completed": true }`
- **THEN** those fields are not updated from client input and the response reflects server-controlled values

#### Scenario: Extended profile fields remain supported
- **WHEN** an authenticated customer PATCHes an already-supported field such as `birth_date`
- **THEN** existing validation and persistence behavior continues to work

### Requirement: Field-level validation on partial updates
Each submitted onboarding field MUST be validated independently. Invalid values MUST return `400` field errors without clearing unrelated stored profile data.

#### Scenario: Invalid phone rejected
- **WHEN** a customer PATCHes a phone that is not exactly 10 digits
- **THEN** the system returns `400` on `phone` and does not modify the stored phone

#### Scenario: Duplicate phone rejected
- **WHEN** a customer PATCHes a phone already used by another customer
- **THEN** the system returns `400` on `phone`

#### Scenario: Invalid gender rejected
- **WHEN** a customer PATCHes `gender` with a value outside `male`, `female`, `other`, `prefer_not_to_say`
- **THEN** the system returns `400` on `gender`

#### Scenario: Invalid occupation rejected
- **WHEN** a customer PATCHes `occupation` outside the existing `CustomerProfile.Occupation` choices
- **THEN** the system returns `400` on `occupation`

#### Scenario: Name trimming and length enforced
- **WHEN** a customer PATCHes names with surrounding whitespace or exceeding max length
- **THEN** the system trims where applicable and enforces existing max-length rules

### Requirement: Object-level authorization for profile updates
A customer MUST only update their own profile. Attempts to access or mutate another customer's profile MUST be denied by authentication and object ownership checks.

#### Scenario: Unauthenticated update rejected
- **WHEN** a client calls PATCH profile without a valid token
- **THEN** the system returns `401 Unauthorized`

#### Scenario: Non-customer token rejected
- **WHEN** an authenticated user without `customer_profile` calls PATCH profile
- **THEN** the system returns `403 Forbidden`

### Requirement: Idempotent and safe repeat submissions
Submitting the same valid onboarding payload multiple times MUST leave the profile in a consistent state and MUST NOT create duplicate records or corrupt unrelated fields.

#### Scenario: Repeated name update is safe
- **WHEN** a customer submits the same `{ "first_name": "John", "last_name": "Doe" }` twice
- **THEN** both requests succeed with identical resulting stored values

### Requirement: Existing customer profile data is preserved
Customers registered before this change MUST retain all existing stored values. Progressive onboarding MUST only prompt for fields that are actually missing; the backend MUST NOT overwrite populated legacy values with null unless the client explicitly clears a nullable field through a supported contract.

#### Scenario: Legacy fully populated customer unchanged by login
- **WHEN** an existing customer with phone, occupation, and `is_bachelor` already set logs in and fetches profile
- **THEN** all previously stored values are returned unchanged

#### Scenario: Partial legacy customer fills only missing fields
- **WHEN** an existing customer missing only `gender` PATCHes `{ "gender": "female" }`
- **THEN** only `gender` is added/updated; existing phone and name remain intact

### Requirement: Marital status maps to existing is_bachelor field
The system does not introduce a new `marital_status` column. Onboarding UX that references marital status MUST use the existing `is_bachelor` boolean field with its current semantics. API field names remain snake_case (`is_bachelor`).

#### Scenario: Bachelor status collected progressively
- **WHEN** the frontend collects marital/bachelor status and PATCHes `{ "is_bachelor": false }`
- **THEN** the system stores the boolean on `CustomerProfile.is_bachelor`
