## MODIFIED Requirements

### Requirement: Admin can list customers with basic information

The system SHALL provide a verified-admin web API collection at `/api/v1/web/customers/` that returns a paginated list of customer profiles. Each list item MUST include at least: customer `public_id`, display name, email, phone, `profile_picture_url` (nullable), account active flag, email verification status, registration timestamp (`User.date_joined`), and current meal package summary when an active order exists (package name and order `public_id` or null). Unauthenticated callers MUST receive `401`. Authenticated non-admin callers MUST receive `403`. When a customer has a stored profile picture, `profile_picture_url` MUST be the media/S3 URL for that picture. When absent, it MUST be `null`.

#### Scenario: Verified admin lists customers

- **WHEN** a verified admin requests `GET /api/v1/web/customers/`
- **THEN** the system responds `200` with a paginated list of customers including the basic information fields above

#### Scenario: Unauthenticated list denied

- **WHEN** an unauthenticated client requests the admin customer list
- **THEN** the system responds `401 Unauthorized`

#### Scenario: Non-admin authenticated user denied

- **WHEN** an authenticated customer without verified-admin permission requests the admin customer list
- **THEN** the system responds `403 Forbidden`

#### Scenario: Profile picture absent

- **WHEN** a customer has no profile picture stored
- **THEN** the list item MUST include `profile_picture_url` with value `null`

#### Scenario: Profile picture present

- **WHEN** a customer has a stored profile picture
- **THEN** the list item MUST include `profile_picture_url` with the non-null media/S3 URL for that picture

## ADDED Requirements

### Requirement: Admin customer overview includes real profile picture URL

The admin customer overview/detail payload MUST include `profile_picture_url` that reflects the stored customer profile picture media URL when present, or `null` when absent. The system MUST NOT hardcode this field to `null` when a picture exists.

#### Scenario: Overview with picture

- **WHEN** a verified admin requests overview for a customer who has uploaded a profile picture
- **THEN** `profile_picture_url` is the non-null media/S3 URL

#### Scenario: Overview without picture

- **WHEN** a verified admin requests overview for a customer without a profile picture
- **THEN** `profile_picture_url` is `null`
