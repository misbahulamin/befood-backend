## ADDED Requirements

### Requirement: Customer global search endpoint
The system SHALL expose `GET /api/v1/search` (trailing slash per project convention) that accepts a required `q` query parameter and returns a JSON payload including the echoed `query` (original and/or normalized as documented) and a ranked `results` list. The endpoint MUST be usable by guests and authenticated customers.

#### Scenario: Successful multi-type search
- **WHEN** a client searches `q=chicken` and matching package, food, and instant meal documents exist
- **THEN** the response includes results that may contain multiple `type` values in one list

#### Scenario: Missing query rejected
- **WHEN** a client calls search without `q` or with only whitespace that normalizes to empty
- **THEN** the system returns `400` or `422` validation errors, or a documented empty-query response without treating it as a server error

### Requirement: Query normalization before matching
Before matching, the system MUST normalize `q` by trimming, collapsing extra spaces, stripping ignorable punctuation, lowercasing Latin letters, and preserving Bangla characters. Matching MUST use the normalized form.

#### Scenario: Whitespace and case normalized
- **WHEN** a client searches `q="  Kacchi  "`
- **THEN** matching runs against normalized `kacchi` and can return the Kacchi document as a top result

#### Scenario: Bangla query preserved
- **WHEN** a client searches `q=ভাত`
- **THEN** the system can match documents/keywords for rice without requiring Latin transliteration in the query

### Requirement: Multi-strategy matching with ranked priority
The system MUST rank results using this priority order: exact name/keyword match, then starts-with match, then partial/substring match, then synonym/keyword transliteration match, then fuzzy/typo-tolerant match, with popularity/relevance as a final tie-breaker. Exact matches MUST appear before weaker fuzzy-only matches for the same query.

#### Scenario: Exact Bangla match ranks first
- **WHEN** a client searches `কাচ্চি` and an exact Kacchi document exists alongside weaker biryani-related documents
- **THEN** the Kacchi document appears before lower-priority related results

#### Scenario: Partial match returns related chicken dishes
- **WHEN** a client searches `চিক` and documents titled like chicken curry / biryani / khichuri exist with matching prefixes or substrings
- **THEN** those relevant chicken documents are eligible to appear in results

#### Scenario: Multilingual synonyms resolve to the same item
- **WHEN** a client searches any of `ভাত`, `vat`, `bhat`, or `rice` and the rice document includes those keywords
- **THEN** the rice document is returned for each of those queries

#### Scenario: Typo-tolerant fuzzy match
- **WHEN** a client searches `kachci` or `chiken` and close catalog titles/keywords exist
- **THEN** the system returns the closest relevant documents via fuzzy matching when stronger exact/prefix hits are absent or insufficient

### Requirement: Result card fields for navigation and display
Each result item MUST include at least `type`, `public_id`, and a primary `name` (and `name_en` when available). The API SHOULD include short description, image URL, price, currency, and availability when known so the dropdown can render useful cards. Clients MUST navigate using `type` + `public_id`, not internal integer PKs.

#### Scenario: Result exposes public identity and type
- **WHEN** search returns a package result
- **THEN** the item includes `type` `package` and a UUID `public_id` suitable for frontend routing

### Requirement: Result limit for dropdown-sized responses
The system MUST enforce a default small result limit suitable for a dropdown (default 8) and a maximum limit (documented, e.g. 20). Clients MAY pass `limit` within the allowlisted range. Unsupported filters MUST be rejected with `400` when validation is enabled.

#### Scenario: Default limit applied
- **WHEN** a broad query matches more than eight documents and the client omits `limit`
- **THEN** the response returns at most the default number of best-ranked results

### Requirement: Weak or empty primary matches provide recovery hints
When primary ranked results are empty or only weak fuzzy matches exist, the response MUST NOT be a dead-end: it MUST include `did_you_mean` and/or `related` suggestions when candidates exist, so the UI can show “did you mean” / related items instead of only “No Result”.

#### Scenario: Did you mean for near miss
- **WHEN** a client searches a near-miss spelling of Kacchi with no exact hit
- **THEN** the response includes a `did_you_mean` value pointing at Kacchi (or equivalent) when fuzzy confidence is sufficient

#### Scenario: Related results when nothing exact matches
- **WHEN** a query yields zero strong matches but related popular catalog items exist
- **THEN** the response includes a `related` list for the client to display under a no-result message
