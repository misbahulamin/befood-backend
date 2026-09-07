## MODIFIED Requirements

### Requirement: Admin customer search

The system SHALL allow verified admins to search the customer list by name, email, username, and phone via an allowlisted query parameter (for example `q`). Matching MUST be case-insensitive for name, email, and username. Phone matching MUST use the shared admin people-search normalization (optional `+880` / `880` stripping). When `q` is a canonical 36-character UUID, the list MUST also match exact customer `public_id`. Multi-word queries MAY match first-name and last-name pairs. Unsupported or malformed search parameters that fail validation MUST yield `400 Bad Request` and MUST NOT be silently ignored when validation is enabled. Implementation MUST use the shared `build_customer_people_q` helper.

#### Scenario: Search by email fragment

- **WHEN** a verified admin lists customers with `q` matching part of a customer email
- **THEN** only customers whose name, email, username, phone, or matching `public_id` criteria match that query MUST be returned

#### Scenario: Search by phone

- **WHEN** a verified admin lists customers with `q` matching a stored phone number (including common BD prefix variants)
- **THEN** the matching customer MUST appear in the results

#### Scenario: Search by username fragment

- **WHEN** a verified admin lists customers with `q` matching part of a username
- **THEN** the matching customer MUST appear in the results

#### Scenario: Search by customer public_id

- **WHEN** a verified admin lists customers with `q` equal to a customer's canonical `public_id`
- **THEN** that customer MUST appear in the results
