## ADDED Requirements

### Requirement: Ops documentation for meal thumbnail upload failures

The project MUST document how to distinguish gateway body-size failures (`413`) from S3 storage failures and from application image validation failures for `MealCategory.meal_thumbnail` multipart uploads, including the production proxy setting to check (`client_max_body_size` or equivalent) and the smoke-test steps for local vs production.

#### Scenario: Operator follows runbook for production 413 on meal PATCH

- **WHEN** an operator investigates HTTP `413` on `PATCH /meals/{id}/` with multipart thumbnail
- **THEN** documentation MUST instruct them to verify reverse-proxy body size before debugging S3 credentials
- **AND** documentation MUST list a successful smoke path: admin UI or API multipart upload ≤5MB returns success with a storage URL

### Requirement: Frontend admin meal upload path remains compatible

The frontend admin meal create/update flow MUST continue to submit thumbnails as multipart `FormData` with field name `meal_thumbnail`, without forcing a multipart `Content-Type` that omits the boundary. After the production body-limit fix, the admin panel MUST be able to replace a meal thumbnail successfully for files within the 5MB client validation limit.

#### Scenario: Admin replaces meal thumbnail from the panel

- **WHEN** an admin selects a valid jpg/jpeg/png/webp file ≤5MB and saves meal edits that include a new thumbnail
- **THEN** the client MUST send `multipart/form-data` with `meal_thumbnail` set to the file
- **AND** after infrastructure limits allow the body, the request MUST succeed and the UI MUST show the updated thumbnail URL

#### Scenario: Client rejects oversize images before upload

- **WHEN** an admin selects a meal thumbnail larger than 5MB
- **THEN** the frontend MUST block submit with a clear validation message
- **AND** it MUST NOT rely on production `413` as the primary user-facing size error
