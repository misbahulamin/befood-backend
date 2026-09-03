## MODIFIED Requirements

### Requirement: Document Customer List page contract

The frontend documentation MUST specify the Customer List page structure and UI fields: profile image (with null/placeholder handling), name, email, phone, account/verification status, and active package. It MUST document that list/detail `phone` values are returned from the API already in E.164 display form (`+880` + national digits) and that the Admin UI MUST render them as-is without prepending another country code. It MUST document search (name/email/phone, including E.164 paste), filters (active/inactive, has active order / no active order, package-wise, registration date range), pagination, and the primary action to open Customer Details. It MUST include example list request/response shapes and loading, empty, and error state guidance consistent with the existing Admin Panel.

#### Scenario: List UI mapping is documented

- **WHEN** a frontend developer follows the Customer List section of the doc
- **THEN** they can map each table column and filter control to a specific API field or query parameter

#### Scenario: Phone display contract documented

- **WHEN** a frontend developer reads the Customer List phone field guidance
- **THEN** the doc MUST state that `phone` is E.164 from the API and MUST NOT instruct clients to prepend `+880` again
