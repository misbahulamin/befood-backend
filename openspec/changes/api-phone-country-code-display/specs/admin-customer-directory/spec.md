## ADDED Requirements

### Requirement: Admin customer phone fields use E.164 display format

On admin customer list and detail read responses, the `phone` field MUST be returned in E.164-style display format `+880` plus the stored 10 national digits when a phone is present. Storage and any write endpoints for customer phone MUST remain national 10 digits.

#### Scenario: List item phone is E.164

- **WHEN** a verified admin requests `GET /api/v1/web/customers/` for a customer whose stored phone is `1894126298`
- **THEN** that list item’s `phone` MUST equal `+8801894126298`

#### Scenario: Detail phone is E.164

- **WHEN** a verified admin requests `GET /api/v1/web/customers/{public_id}/` for the same customer
- **THEN** the overview `phone` MUST equal `+8801894126298`

## MODIFIED Requirements

### Requirement: Admin customer search

The system SHALL allow verified admins to search the customer list by name, email, and phone via an allowlisted query parameter (for example `q`). Matching MUST be case-insensitive for name and email. Phone search MUST match against stored national digits and MUST also succeed when `q` includes a leading `+880` or `880` country-code prefix for the same number. Unsupported or malformed search parameters that fail validation MUST yield `400 Bad Request` and MUST NOT be silently ignored when validation is enabled.

#### Scenario: Search by email fragment

- **WHEN** a verified admin lists customers with `q` matching part of a customer email
- **THEN** only customers whose name, email, or phone match that query MUST be returned

#### Scenario: Search by phone

- **WHEN** a verified admin lists customers with `q` matching a stored phone number
- **THEN** the matching customer MUST appear in the results

#### Scenario: Search by E.164 phone paste

- **WHEN** a verified admin lists customers with `q=+880` followed by a stored national phone
- **THEN** the matching customer MUST appear in the results
