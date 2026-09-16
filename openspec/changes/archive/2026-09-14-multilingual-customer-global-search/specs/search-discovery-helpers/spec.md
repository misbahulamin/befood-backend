## ADDED Requirements

### Requirement: Popular searches endpoint for empty focus state
The system SHALL expose `GET /api/v1/search/popular` that returns a capped list of popular or trending search terms (and optional linked documents) for the search box empty/focus state. Sources MAY include analytics aggregation and/or admin-curated pins.

#### Scenario: Popular terms available without typing
- **WHEN** a client calls popular searches with no `q`
- **THEN** the response includes terms such as high-demand foods or packages when analytics/curation data exists

#### Scenario: Popular list is capped
- **WHEN** more candidate popular terms exist than the default limit
- **THEN** the response returns at most the documented default number of terms

### Requirement: Recent searches remain a client responsibility in v1
The system MUST document that recent search history for the dropdown is stored and cleared on the client (for example localStorage) in this change. The backend MUST NOT require an authenticated recent-search resource for the v1 global search bar to function.

#### Scenario: Frontend can clear recent searches locally
- **WHEN** a customer clears recent searches in the UI
- **THEN** clearing succeeds without a mandatory backend delete-recent-search call in v1

### Requirement: Popular endpoint is publicly readable and throttled
The popular searches endpoint MUST be usable by guests. The system SHOULD apply request throttling appropriate for a focus-triggered UI call and MUST NOT expose private user search histories in the popular list.

#### Scenario: Guest can load popular searches
- **WHEN** an unauthenticated client requests popular searches
- **THEN** the system returns the public popular list without requiring login
