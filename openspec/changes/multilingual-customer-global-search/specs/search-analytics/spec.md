## ADDED Requirements

### Requirement: Persist search query events
The system SHALL persist search query analytics events including at least `query_original`, `query_normalized`, `result_count`, `is_zero_result`, optional authenticated user reference, optional `session_id`, and `created_at`.

#### Scenario: Zero-result query is stored
- **WHEN** a customer searches `tehari` and no documents match
- **THEN** an analytics event is stored with `is_zero_result=true` and the original/normalized query fields

#### Scenario: Successful query stores result count
- **WHEN** a customer searches `kacchi` and three results are returned
- **THEN** an analytics event is stored with `result_count` reflecting the returned match count and `is_zero_result=false`

### Requirement: Persist click-through events
The system SHALL accept `POST /api/v1/search/events/click` (or equivalent documented path) to record which result was clicked, including clicked document identity (`public_id` / type), optional position, and linkage to the query/session when provided. Guests MAY send a client `session_id`.

#### Scenario: Click on a result is recorded
- **WHEN** a client posts a click event for a package result `public_id` after searching `chicken`
- **THEN** the system stores the click with the document type/id and associated query metadata when supplied

#### Scenario: Invalid click target rejected
- **WHEN** a client posts a click for an unknown `public_id`
- **THEN** the system returns `404` or `422` and does not create a successful click analytics row for that unknown target

### Requirement: Analytics writes are throttled and safe
Anonymous analytics endpoints MUST be rate-limited. The system MUST NOT require secrets in the payload and MUST NOT log authorization headers. Analytics failures MUST NOT break the primary search response when query logging is best-effort after results are computed (if auto-logging on GET search).

#### Scenario: Search still succeeds if analytics write fails
- **WHEN** search matching succeeds but analytics persistence raises an internal error that is handled as best-effort
- **THEN** the client still receives the search results response

### Requirement: Zero-result mining is first-class
The analytics data model and admin summaries MUST make zero-result queries countable and listable so product can detect missing catalog demand (for example many searches for `tehari` with zero results).

#### Scenario: Zero-result queries are aggregatable
- **WHEN** the same normalized zero-result query occurs many times
- **THEN** admin analytics can report that query with a count greater than one
