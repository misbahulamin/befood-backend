## ADDED Requirements

### Requirement: Autocomplete suggestions endpoint
The system SHALL expose `GET /api/v1/search/suggestions` that accepts `q` and returns a short ranked list of suggestion items (title-focused) for the global search dropdown. The endpoint MUST be usable by guests and authenticated customers.

#### Scenario: Prefix suggestions for ka
- **WHEN** a client requests suggestions with `q=ka` and Kacchi-related documents exist
- **THEN** the response includes suggestions such as Kacchi Biryani / Kacchi Meal style titles when they match prefix or keyword rules

### Requirement: Minimum character threshold for suggestions
The system MUST require the normalized query length to be at least 2 characters (configurable) before returning suggestion matches. Shorter queries MUST return an empty suggestion list or a validation error as documented—not arbitrary catalog dumps.

#### Scenario: Single character yields no suggestions
- **WHEN** a client requests suggestions with `q=k`
- **THEN** the system returns no suggestion matches (empty list) or a documented validation response without listing the full catalog

### Requirement: Suggestion payload stays lean and capped
Suggestion responses MUST default to a small page size (default 6, max documented) and MUST include enough fields for display and navigation (`type`, `public_id`, primary name). Heavy nesting is forbidden on this endpoint.

#### Scenario: Default suggestion cap
- **WHEN** many documents match the prefix and the client omits `limit`
- **THEN** at most the default number of suggestions is returned

### Requirement: Client debounce is documented as non-server state
The system MUST document that clients SHOULD debounce suggestion requests (250–350ms) and MUST NOT rely on server sessions to coalesce keystrokes. Each suggestion request is stateless.

#### Scenario: Repeated suggestion calls are independent
- **WHEN** a client sends two suggestion requests for `ka` and `kac` in sequence
- **THEN** each response is computed independently from its own `q` without requiring prior request state
