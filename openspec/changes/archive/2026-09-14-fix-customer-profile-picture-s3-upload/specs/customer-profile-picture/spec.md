## ADDED Requirements

### Requirement: Customer can upload a profile picture

The system SHALL allow an authenticated user with a customer profile to upload a profile picture via `POST /api/v1/user_management/customer/profile/image/` using `multipart/form-data` with field name `image`. On success the system MUST store the file through Django’s default media storage (AWS S3 when `USE_S3_MEDIA` is enabled) and respond with HTTP `200` or `201` including `profile_image_url` (absolute HTTPS media/S3 URL when S3 is enabled) and an optional `message`. Unauthenticated callers MUST receive `401`. Authenticated users without a customer profile MUST be denied (`403` or the existing `HasCustomerProfile` denial). A customer MUST only be able to upload to their own profile (bound to `request.user.customer_profile`).

#### Scenario: Successful upload

- **WHEN** an authenticated customer posts a valid image file as `image` to the profile image endpoint
- **THEN** the system stores the file via default media storage, updates the customer profile picture field, and returns `profile_image_url` pointing at the stored object

#### Scenario: Unauthenticated upload denied

- **WHEN** an unauthenticated client posts to the profile image endpoint
- **THEN** the system responds `401 Unauthorized`

#### Scenario: Non-customer authenticated user denied

- **WHEN** an authenticated user without a customer profile posts to the profile image endpoint
- **THEN** the system denies the request and MUST NOT store a file for another account

### Requirement: Profile picture object key layout

The system MUST store profile pictures under a scalable key prefix `profiles/users/{folder_slug}/profile_picture.{ext}` where `{ext}` is a validated extension (`jpg`, `jpeg`, `png`, or `webp`). The `{folder_slug}` MUST be derived as follows: (1) if the user has a non-empty display name (first and/or last name), sanitize it to lowercase with spaces replaced by `_` and non-alphanumeric characters removed or replaced; (2) otherwise use the email local-part before `@` with the same sanitization; (3) append a short unique suffix from the customer `public_id` so distinct users never share the same folder. The logical filename MUST be `profile_picture.{ext}` (not the raw client upload name).

#### Scenario: User with name

- **WHEN** a customer named `Abdul Rahim` uploads a JPEG profile picture
- **THEN** the stored object key MUST match `profiles/users/abdul_rahim_<public_id8>/profile_picture.jpg` (or `.jpeg` if that extension is preserved from the upload)

#### Scenario: User without name uses email local-part

- **WHEN** a customer with empty names and email `rahim123@gmail.com` uploads a PNG profile picture
- **THEN** the stored object key MUST match `profiles/users/rahim123_<public_id8>/profile_picture.png`

#### Scenario: Collision safety for identical names

- **WHEN** two different customers share the same display name and both upload profile pictures
- **THEN** each MUST receive a distinct folder slug (via `public_id` suffix) and MUST NOT overwrite the other’s object

### Requirement: Profile picture validation

The system MUST reject profile picture uploads that are not an allowed image type (`jpg`, `jpeg`, `png`, `webp`) or that exceed the maximum size of 2 MiB. Invalid uploads MUST NOT update the stored profile picture field.

#### Scenario: Reject disallowed type

- **WHEN** a customer uploads a file with extension `gif` or another non-allowed type
- **THEN** the system responds with a client error and leaves any existing profile picture unchanged

#### Scenario: Reject oversized file

- **WHEN** a customer uploads an otherwise valid image larger than 2 MiB
- **THEN** the system responds with a client error and leaves any existing profile picture unchanged

### Requirement: Replace and clear profile picture

When a customer uploads a new profile picture while one already exists, the system MUST replace the field value and MUST delete or otherwise remove the previous media storage object when feasible. When the customer clears the picture (for example by sending `profile_image_url: null` on the existing profile update endpoint), the system MUST remove the stored file reference and delete the previous media object when feasible, and subsequent reads MUST return a null picture URL.

#### Scenario: Replace existing picture

- **WHEN** a customer who already has a profile picture uploads a new valid image
- **THEN** the profile picture field points at the new object and the previous storage object is deleted or no longer referenced

#### Scenario: Clear profile picture

- **WHEN** an authenticated customer clears their profile picture via the supported clear path
- **THEN** the profile picture field is empty and `profile_image_url` is `null` on subsequent profile reads

### Requirement: Extended profile exposes profile_image_url

The customer extended profile GET (and successful PATCH) response MUST include `profile_image_url` as a nullable string reflecting the current stored picture URL (or `null` when absent). The system MUST NOT accept arbitrary client-supplied remote URLs or data URLs as the stored picture via PATCH; only the dedicated upload endpoint (and the clear/`null` path) MAY change the stored picture.

#### Scenario: GET returns stored URL

- **WHEN** an authenticated customer with a stored profile picture requests `GET /api/v1/user_management/customer/profile/`
- **THEN** the response includes a non-null `profile_image_url` for that picture

#### Scenario: GET returns null when absent

- **WHEN** an authenticated customer without a profile picture requests the extended profile
- **THEN** `profile_image_url` is `null`

#### Scenario: Reject unsafe URL assignment on PATCH

- **WHEN** a customer PATCHes `profile_image_url` to a data URL or arbitrary remote URL
- **THEN** the system MUST NOT persist that string as the ImageField value
