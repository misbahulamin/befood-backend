## ADDED Requirements

### Requirement: Verified admin can manage search documents
The system SHALL expose verified-admin web APIs under `/api/v1/web/search/documents/` to list, create, retrieve, update, and deactivate/delete searchable documents. List endpoints MUST support pagination, deterministic ordering, and allowlisted filters such as `document_type`, `is_active`, and text `q`.

#### Scenario: Admin creates a food document with titles
- **WHEN** a verified admin posts a valid food document with `title_en` and `title_bn`
- **THEN** the system returns `201 Created` with the document `public_id`

#### Scenario: Unverified user denied
- **WHEN** a non-admin client attempts to create or mutate search documents
- **THEN** the system returns `401` or `403` as appropriate

### Requirement: Verified admin can manage keywords on a document
The system SHALL allow verified admins to add, list, and remove keywords for a document. Keyword writes MUST normalize values and enforce uniqueness per document.

#### Scenario: Admin adds Banglish keywords to rice
- **WHEN** a verified admin adds keywords `vat`, `bhat`, and `rice` to the rice document
- **THEN** subsequent customer searches for those terms can resolve to that document

#### Scenario: Admin removes a keyword
- **WHEN** a verified admin deletes a keyword from a document
- **THEN** that normalized keyword no longer contributes matches for that document

### Requirement: Admin analytics summary endpoints
The system SHALL provide verified-admin analytics summary endpoints (for example under `/api/v1/web/search/analytics/`) that expose top queries, zero-result queries, and top clicked documents over an allowlisted date range, with pagination where lists can be large.

#### Scenario: Top zero-result queries
- **WHEN** a verified admin requests zero-result analytics for a date range that includes many `tehari` searches with no hits
- **THEN** the summary lists `tehari` (normalized) with an aggregate count

#### Scenario: Unsupported analytics filter rejected
- **WHEN** a client passes an unsupported filter operator or unknown query parameter that fails validation
- **THEN** the system returns `400 Bad Request` and does not silently ignore the bad filter when validation is enabled

### Requirement: Public identifiers on admin resources
Admin document APIs MUST identify documents by `public_id` in paths and responses. Integer primary keys MUST NOT be required by admin clients for these resources.

#### Scenario: Retrieve by public_id
- **WHEN** a verified admin retrieves `GET /api/v1/web/search/documents/{public_id}/`
- **THEN** the response returns that document’s details including keywords summary or nested keyword collection as documented
