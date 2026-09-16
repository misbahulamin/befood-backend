## ADDED Requirements

### Requirement: Admin UI displays API phone without prepending country code

The Admin Panel MUST render customer phone values returned by the API as-is for on-screen tables and detail views (including `/admin/customers`). The frontend MUST NOT prepend `+880` (or another country code) to phone strings that already include the country code from the API.

#### Scenario: Customer list shows E.164 from API

- **WHEN** the admin customers API returns `phone` as `+8801894126298`
- **THEN** the Customer List Phone column MUST display `+8801894126298` without an additional `+880` prefix

#### Scenario: No double country code

- **WHEN** a phone value from the API already starts with `+880`
- **THEN** admin display helpers MUST NOT produce a string beginning with `+880+880`

### Requirement: Print and PDF use readable phone formatting

Admin print sheets and download/PDF views that show customer phones (including kitchen order details print) MUST display a readable hyphenated form such as `+880-1894-126298`. That formatting MUST be applied only as a presentation step for print/PDF and MUST NOT break existing table or print layout structure.

#### Scenario: Kitchen print sheet readable phone

- **WHEN** an admin prints kitchen order details for a row whose phone is `+8801894126298`
- **THEN** the printed phone MUST appear as `+880-1894-126298` (or an equivalent documented readable pattern using the shared print helper)

#### Scenario: Print layout preserved

- **WHEN** readable phone formatting is applied on a print sheet
- **THEN** existing column structure and page layout MUST remain usable (no new card wrappers or layout breakage required solely for phone formatting)

### Requirement: Profile edit maps E.164 to local input without changing write contract

Customer-facing profile edit UIs that collect Bangladesh mobile numbers MUST continue to present a local `01XXXXXXXXX` style input when the profile API returns E.164, and MUST submit national 10-digit values expected by the write API.

#### Scenario: Profile form shows local digits

- **WHEN** the profile API returns `phone` as `+8801712345678`
- **THEN** the profile contact form MUST show an editable local form such as `01712345678` (or the project’s existing `01…` display helper output)

#### Scenario: Profile save sends national digits

- **WHEN** the user saves a valid local phone from the profile form
- **THEN** the PATCH/update payload phone field MUST be the 10-digit national value, not the E.164 display string
