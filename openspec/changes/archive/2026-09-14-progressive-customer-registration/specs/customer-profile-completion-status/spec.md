## ADDED Requirements

### Requirement: Onboarding completion metadata exposed to authenticated customers
The system SHALL expose derived onboarding completion metadata so clients can determine which profile information is already present and which fields remain to collect. Metadata MUST be available on at least one existing authenticated customer endpoint (`GET /user_management/me/` and/or `GET /user_management/customer/profile/`). No duplicate standalone endpoint is required if existing endpoints are extended.

#### Scenario: Missing fields reported for new minimal registrant
- **WHEN** a verified customer who registered with email-only fetches `/me/` or profile
- **THEN** the response includes onboarding completion data listing missing fields among at least: `first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`, `gender`

#### Scenario: Fully onboarded customer reports complete
- **WHEN** a customer has non-empty `first_name` and `last_name`, a stored phone, occupation, `is_bachelor` set (true or false), and `gender` set
- **THEN** onboarding completion reports `completed: true` and an empty `missing_fields` list

#### Scenario: Partially completed profile lists only missing items
- **WHEN** a customer has name and phone but no gender
- **THEN** `missing_fields` includes `gender` (and any other unset onboarding fields) but not `first_name`, `last_name`, or `phone`

### Requirement: Onboarding completion is derived not stored redundantly
Onboarding `completed` and `missing_fields` MUST be derived from current `User` and `CustomerProfile` values at read time. The system MUST NOT add redundant boolean columns solely for onboarding completion unless derivation is proven unsafe or too expensive.

#### Scenario: Completion updates after PATCH without separate write
- **WHEN** a customer PATCHes a previously missing onboarding field
- **THEN** a subsequent GET reflects the reduced `missing_fields` list without requiring a separate completion-status write endpoint

### Requirement: Onboarding completion is separate from extended profile completion
The existing extended profile completion metrics (`profile_completion_percentage`, `profile_completed` based on food/delivery/emergency fields) MUST remain distinct from onboarding completion metadata. Clients MUST be able to distinguish account registration complete (email verified) from onboarding profile complete and from extended profile complete.

#### Scenario: Onboarding incomplete but extended metrics may differ
- **WHEN** a customer has completed onboarding fields but lacks extended profile fields such as `birth_date`
- **THEN** onboarding completion reports `completed: true` while existing extended `profile_completed` may remain `false`

#### Scenario: Optional completion percentage for onboarding
- **WHEN** the API includes an onboarding completion percentage
- **THEN** it is derived from the count of populated onboarding fields and documented as informational only

### Requirement: Existing customers with legacy registration data appear complete
Customers who registered under the legacy flow with required phone, occupation, and `is_bachelor` MUST be treated as having those onboarding fields present. Missing onboarding metadata MUST reflect only genuinely absent values (for example empty `first_name` or unset `gender`).

#### Scenario: Legacy customer missing only gender
- **WHEN** a pre-change customer has phone, occupation, and `is_bachelor` populated but `gender` is null
- **THEN** `missing_fields` contains `gender` and not `phone`, `occupation`, or `is_bachelor`

#### Scenario: Legacy fully populated customer
- **WHEN** a pre-change customer has all onboarding fields populated
- **THEN** onboarding completion reports `completed: true`
