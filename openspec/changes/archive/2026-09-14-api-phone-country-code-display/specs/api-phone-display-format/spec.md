## ADDED Requirements

### Requirement: Shared E.164 phone formatting for API reads

The system SHALL provide a shared Bangladesh phone formatter that converts a stored national 10-digit phone into an E.164-style display string `+880` followed by those 10 digits. JSON API responses that expose customer (or customer emergency contact) phone numbers for display MUST use this formatter. Empty or null stored phones MUST remain null/empty in the response. Write/PATCH request bodies and database storage MUST continue to use national 10-digit values validated by the existing Bangladesh phone validator. The formatter MUST be idempotent for inputs that already include `+880` or a leading `880` country code.

#### Scenario: National digits become E.164

- **WHEN** a stored customer phone is `1894126298`
- **THEN** an API read that returns that phone MUST yield `+8801894126298`

#### Scenario: Empty phone stays empty

- **WHEN** a stored customer phone is null or blank
- **THEN** the API read MUST return null or omit/empty per the endpoint’s existing nullability contract (MUST NOT invent a country code)

#### Scenario: Write path unchanged

- **WHEN** a client PATCHes a profile phone with national digits `1711111111`
- **THEN** the system MUST store `1711111111` and MUST NOT require the client to send `+880` in the write body

### Requirement: Readable phone formatting for print and email

The system SHALL provide a shared readable Bangladesh phone formatter that produces `+880-XXXX-XXXXXX` (hyphenated) from a national or E.164 input. Printable documents, PDF invoice contexts, and operator-facing email/notification templates that include a customer phone MUST use this readable form. JSON list/detail APIs for on-screen tables MUST use the non-hyphenated E.164 form from the previous requirement, not the hyphenated readable form.

#### Scenario: Readable form for documents

- **WHEN** an invoice or notification template includes a customer phone stored as `1894126298`
- **THEN** the rendered phone MUST be `+880-1894-126298`

#### Scenario: API JSON stays compact E.164

- **WHEN** an admin list API returns a customer `phone` field
- **THEN** the value MUST be `+8801894126298` without internal hyphens

### Requirement: Phone search accepts dial-code prefixes

When an admin search parameter matches against stored national phone digits, the system MUST normalize query terms that begin with `+880` or `880` by stripping that country-code prefix before comparison so operators can paste E.164 strings and still find the customer.

#### Scenario: Search with E.164 paste

- **WHEN** a verified admin searches customers with `q=+8801894126298` for a profile stored as `1894126298`
- **THEN** that customer MUST appear in the results

#### Scenario: Search with national digits

- **WHEN** a verified admin searches with `q=1894126298` for the same stored phone
- **THEN** that customer MUST appear in the results

### Requirement: Cross-surface consistency for customer phone emission

Every backend response path that returns a customer phone for display (including admin customers, customer profile/auth payloads, order `customer_phone`, meal-demand/kitchen customer rows, and wallet funding customer phone fields) MUST apply the shared E.164 formatter. Duplicate inline country-code concatenation outside the shared helpers MUST NOT be introduced.

#### Scenario: Order and customer list agree

- **WHEN** the same customer’s phone is returned from the admin customer list and from an admin order payload’s customer phone field
- **THEN** both values MUST be identical E.164 strings for the same stored national number
