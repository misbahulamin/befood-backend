## ADDED Requirements

### Requirement: Proxy accepts meal thumbnail multipart bodies up to product max

The production reverse proxy in front of the BeFood API MUST accept authenticated multipart requests whose total body size is large enough for a meal thumbnail up to the product maximum of 5MB (plus reasonable multipart overhead). Valid meal thumbnail uploads MUST NOT be rejected with HTTP `413 Request Entity Too Large` by the gateway.

#### Scenario: Production meal thumbnail PATCH under 5MB succeeds past the gateway

- **WHEN** a verified admin sends `PATCH /meals/{public_id}/` as `multipart/form-data` including a `meal_thumbnail` image file whose size is ≤ 5MB
- **THEN** the reverse proxy MUST forward the request to the application
- **AND** the response MUST NOT be HTTP `413` from the gateway

#### Scenario: Oversized meal thumbnail is rejected by application rules, not as gateway 413

- **WHEN** a verified admin attempts to upload a meal thumbnail larger than 5MB and the request body is still within the configured proxy limit
- **THEN** the client MUST receive an application validation failure (frontend and/or HTTP `400` with `meal_thumbnail` errors)
- **AND** the failure MUST NOT be reported solely as gateway HTTP `413` for the product size rule

### Requirement: Django upload settings do not undercut the meal image contract

When Django request upload settings are configured explicitly for this project, they MUST allow request bodies at least as large as the meal thumbnail product maximum (5MB). Meal thumbnail size enforcement MUST remain in meal image validation (5MB), not by silently failing with a gateway-style `413` from the application stack.

#### Scenario: Explicit Django body allowance covers meal uploads

- **WHEN** Django `DATA_UPLOAD_MAX_MEMORY_SIZE` (or equivalent documented upload settings) are set for production
- **THEN** those settings MUST be ≥ the 5MB meal thumbnail product maximum
- **AND** meal create/update serializers MUST continue to reject images larger than 5MB with field validation errors
