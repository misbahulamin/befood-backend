## ADDED Requirements

### Requirement: Verified admin can CRUD asset categories via API

The system SHALL expose a token-authenticated admin HTTP API for asset categories under `/assets/categories/` using `IsVerifiedAdmin`. Verified admins MUST be able to create, list, retrieve, partially update, and soft-deactivate (or delete-as-retire) categories identified by `public_id`. Responses MUST include `public_id` and MUST NOT expose operations to anonymous users or non-admin authenticated users. Unverified admins MUST be denied.

#### Scenario: Create category

- **WHEN** a verified admin `POST`s `/assets/categories/` with a unique `name`
- **THEN** the system returns `201 Created` with a `public_id` and the category payload

#### Scenario: List categories

- **WHEN** a verified admin `GET`s `/assets/categories/`
- **THEN** the system returns `200 OK` with a paginated list of categories

#### Scenario: Retrieve by public_id

- **WHEN** a verified admin `GET`s `/assets/categories/{public_id}/`
- **THEN** the system returns `200 OK` with the category detail

#### Scenario: Non-admin denied on categories

- **WHEN** an anonymous client or non-admin authenticated user calls category create, list, update, or delete
- **THEN** the system denies access (`401` or `403` as applicable)

#### Scenario: Unverified admin denied

- **WHEN** an authenticated user with an unverified `AdminProfile` calls the category API
- **THEN** the system returns `403 Forbidden`

### Requirement: Verified admin can CRUD permanent assets via API

The system SHALL expose a token-authenticated admin HTTP API for permanent assets under `/assets/` using `IsVerifiedAdmin`. Verified admins MUST be able to create, list, retrieve, partially update, and retire assets identified by `public_id`. Create/update payloads MUST accept category by `category_public_id`. Responses MUST include `public_id`, category summary (at least `public_id` and `name`), status, quantity, asset_tag, and timestamps. Integer primary keys MUST NOT be required in client URLs.

#### Scenario: Create permanent asset

- **WHEN** a verified admin `POST`s `/assets/` with `name`, `category_public_id`, `asset_tag`, and optional ops fields
- **THEN** the system returns `201 Created` with `public_id` and the stored fields

#### Scenario: Retrieve asset by public_id

- **WHEN** a verified admin `GET`s `/assets/{public_id}/`
- **THEN** the system returns `200 OK` with the full admin asset payload

#### Scenario: Partial update status

- **WHEN** a verified admin `PATCH`es `/assets/{public_id}/` with `status` `under_maintenance`
- **THEN** the system returns `200 OK` and persists the new status

#### Scenario: Retire via DELETE

- **WHEN** a verified admin `DELETE`s `/assets/{public_id}/`
- **THEN** the system returns `204 No Content`, sets `is_active` to false, and keeps the row for history (soft retire)

#### Scenario: Non-admin denied on assets

- **WHEN** an anonymous client or non-admin authenticated user calls asset create, list, update, or delete
- **THEN** the system denies access (`401` or `403` as applicable)

### Requirement: Admin asset list supports filters, search, sort, and pagination

The admin asset list MUST support filtering by `status`, `category_public_id` (or equivalent category filter), `is_active`, and optional `outlet` when set; text search across `name`, `asset_tag`, `serial_number`, `brand`, and `model`; deterministic ordering; and pagination with a default page size and a maximum page size. Default list MUST return active assets only unless `include_inactive=true` (or `is_active` filter) is provided.

#### Scenario: Filter by status

- **WHEN** a verified admin lists assets with `status=in_service`
- **THEN** the response includes only assets with status `in_service`

#### Scenario: Filter by category

- **WHEN** a verified admin lists assets with a specific category public id filter
- **THEN** the response includes only assets in that category

#### Scenario: Search by asset tag

- **WHEN** a verified admin lists assets with search query matching an `asset_tag`
- **THEN** the matching asset appears in the results

#### Scenario: Default excludes inactive

- **WHEN** a verified admin lists assets without inactive inclusion
- **THEN** soft-retired (`is_active=false`) assets are omitted

#### Scenario: Include inactive

- **WHEN** a verified admin lists assets with inactive inclusion enabled
- **THEN** inactive assets may appear in the results

### Requirement: Admin writes enforce catalog validation

Admin create and update MUST reject payloads that violate catalog rules: missing name, missing/invalid category, duplicate `asset_tag`, invalid status, `quantity` &lt; 1, unknown fields that would mass-assign protected identity, or warranty date before purchase date when both are set. Errors MUST use the project's standard API error shape and appropriate `4xx` status (typically `400`/`422`).

#### Scenario: Reject missing category

- **WHEN** a verified admin creates an asset without a valid `category_public_id`
- **THEN** the system returns a validation error and does not create the asset

#### Scenario: Reject duplicate tag on update

- **WHEN** a verified admin patches an asset to an `asset_tag` owned by another asset
- **THEN** the system returns a validation error

### Requirement: No public or mobile permanent-asset endpoints in this change

The system MUST NOT expose unauthenticated public feeds or mobile operator endpoints for permanent assets in this change. All permanent-asset HTTP APIs introduced here MUST require verified admin access.

#### Scenario: No anonymous asset catalog

- **WHEN** an anonymous client requests `/assets/` or `/assets/categories/`
- **THEN** the system denies access with `401 Unauthorized`

### Requirement: Admin API documentation is provided

The change MUST document the admin endpoint grid, Token auth (`IsVerifiedAdmin`), request/response examples, field meanings, filters, status values, soft-retire behavior, and the explicit non-consumable boundary versus food inventory, in frontend-oriented documentation under the assets app docs.

#### Scenario: Frontend admin doc exists

- **WHEN** the change is completed
- **THEN** frontend documentation describes the permanent asset admin CRUD contract with auth, workflows, and examples sufficient for the frontend admin app
