## ADDED Requirements

### Requirement: Customer global search frontend contract documentation
The system SHALL ship frontend contract documentation under `search/docs/frontend/` (or equivalent app docs path) describing how the website global search bar calls search, suggestions, popular, and click analytics endpoints. Docs MUST include base paths, auth expectations (guest-friendly), query parameters, debounce guidance (250–350ms), minimum characters for suggestions, and example request/response payloads.

#### Scenario: Docs cover debounce and min characters
- **WHEN** a frontend engineer reads the customer search docs
- **THEN** the docs state to debounce suggestion/search requests by 250–350ms and to call suggestions only after at least 2 characters

### Requirement: Docs describe grouped dropdown UX and navigation
The documentation MUST describe grouping results by `type` (for example Meals vs Packages), showing 5–8 best results in the dropdown, offering a “view all results” path, and navigating with `type` + `public_id`. Docs MUST list expected card fields (image, name, type, short description, price, availability) and which are optional.

#### Scenario: Docs explain type-based routing
- **WHEN** a result has `type` `package` and a `public_id`
- **THEN** the docs specify the frontend should route to the corresponding package page using that public identifier

### Requirement: Docs cover empty, popular, recent, and no-result states
The documentation MUST specify: empty focus shows popular searches; recent searches are client-stored and clearable; no-result UI uses `did_you_mean` / `related` instead of only a dead “No Result” message; and click events SHOULD be posted when a user selects a result.

#### Scenario: Docs describe did-you-mean handling
- **WHEN** search returns an empty `results` array but includes `did_you_mean` or `related`
- **THEN** the docs instruct the UI to render those recovery hints to the customer

### Requirement: Backend technical docs accompany the feature
The system SHALL also provide backend technical documentation covering models, matching/ranking rules, admin workflows, analytics fields, error map, and how to verify via Swagger/tests.

#### Scenario: Backend docs explain normalization and ranking
- **WHEN** a backend engineer reads the search backend docs
- **THEN** the docs explain normalize → match tiers → rank → respond, including multilingual keyword examples
