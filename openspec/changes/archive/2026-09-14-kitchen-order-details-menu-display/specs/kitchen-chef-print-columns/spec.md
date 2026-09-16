## ADDED Requirements

### Requirement: Chef PDF package table shows only package and final meals

The Admin Kitchen Today Chef print/download sheet SHALL render the package-wise summary table with exactly two data columns: **প্যাকেজ** and **চূড়ান্ত মিল**. The Chef PDF MUST NOT include **প্রত্যাশিত** (expected) or **মিল অফ** (meal off) columns. The on-screen Kitchen Today dashboard MAY continue to show Expected and Meal off for operators.

#### Scenario: Chef download omits expected and meal-off columns

- **WHEN** a verified admin clicks Chef and downloads the kitchen PDF for the current filters
- **THEN** the package summary table headers are প্যাকেজ and চূড়ান্ত মিল only, with no প্রত্যাশিত or মিল অফ columns

#### Scenario: On-screen dashboard may still show expected and meal-off

- **WHEN** an admin views the Kitchen Today package-wise summary on screen
- **THEN** Expected and Meal off columns MAY remain visible on the dashboard without appearing on the Chef PDF

### Requirement: Item-wise cooking section unchanged on Chef PDF

The Chef print/PDF **আইটেম অনুযায়ী রান্না (কোন আইটেমে কত জন)** section MUST remain as currently specified (item name, total people, package contributions, quantity when available). This change MUST NOT alter that table’s columns or aggregation semantics.

#### Scenario: Item-wise table still present

- **WHEN** a Chef PDF is generated for a slot with ingredient rows
- **THEN** the item-wise cooking section still lists those items with people counts and package breakdown as before
