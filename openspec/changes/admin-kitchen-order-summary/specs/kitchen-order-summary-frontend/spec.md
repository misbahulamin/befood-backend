## ADDED Requirements

### Requirement: Kitchen Today dashboard shows package-wise and item-wise summary

The Admin Kitchen Today page (`/admin/kitchen/today`) SHALL display, for the active filters, a package-wise meal summary section and an item-wise cooking calculation section using the kitchen cooking summary API. The package section MUST show per-package customer/final meal counts in a readable format. The item section MUST show each food item’s consolidated `customer_count` and which packages contribute to that count. Existing overall headcount and confirmation status indicators MUST remain visible.

#### Scenario: Admin views Student and Regular summary

- **WHEN** a verified admin opens Kitchen Today for a slot where Student has 10 final meals and Regular has 8
- **THEN** the package-wise section lists both packages with those final counts and the item-wise section lists consolidated items for that slot

#### Scenario: Incomplete menu warning

- **WHEN** the summary response has `ingredients_incomplete=true`
- **THEN** the dashboard shows a clear warning that item data may be incomplete

### Requirement: Dashboard filters drive summary and print

The Kitchen Today UI SHALL provide filters for service date, meal period (`lunch`|`dinner`), and package (optional, all packages when unset). Changing filters and applying them MUST refetch the summary API with those query params. Print and download actions MUST use the currently loaded filtered summary data, not an unfiltered refetch.

#### Scenario: Package filter updates both sections

- **WHEN** the admin selects a single package filter and applies it
- **THEN** both the package-wise and item-wise sections reflect only that package’s summary data from the API

#### Scenario: Reset restores default slot

- **WHEN** the admin resets filters
- **THEN** the page reloads the server default kitchen slot (today + inferred meal period) without a forced package filter

### Requirement: Printable kitchen sheet from dashboard data

The Admin Kitchen Today UI SHALL allow the admin to print or download a kitchen sheet generated from the currently displayed summary. The sheet layout MUST include: Section 1 package-wise summary; Section 2 item-wise cooking calculation (item name, total customer count, package contributions, and kg quantity when available); Section 3 prep notes (confirmation status and incomplete-menu warning when applicable). The layout MUST be optimized for printing and SHOULD fit on one page for typical daily package/item counts without truncating numeric totals.

#### Scenario: Print uses on-screen filtered data

- **WHEN** the admin has filtered to dinner on date `D` for one package and triggers print/download
- **THEN** the generated sheet shows that date, dinner, that package’s summary, and the corresponding item-wise rows

#### Scenario: Sheet remains readable without inventing items

- **WHEN** package counts exist but the ingredient list is empty or incomplete
- **THEN** the sheet still prints package-wise counts and shows the incomplete-menu note rather than fabricating food items
