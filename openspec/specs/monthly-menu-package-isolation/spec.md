## Purpose

Keep monthly menu schedules isolated per meal package and cycle month so admin publish/edit/sync and customer reads never cross-contaminate sibling packages.

## Requirements

### Requirement: Menu schedules are isolated per meal package and month

The system SHALL store and mutate monthly menu schedules only in the scope of a single `MealCyclePlan` (one meal package within one calendar cycle month). Creating, assigning, publishing, unpublishing, deleting, or sync-applying a schedule for one package MUST NOT create, delete, hide, overwrite, or change the status or slot contents of any other package’s schedule for the same or any other month.

#### Scenario: Publish Premium July leaves Regular July intact

- **WHEN** Regular Package already has a published July menu and a verified admin publishes Premium Package’s July menu
- **THEN** Regular Package’s July schedule remains published with the same slot assignments and prices as before

#### Scenario: Replace assignments on one package does not clear another

- **WHEN** a verified admin replaces draft assignments on Student Package’s July schedule
- **THEN** Premium and Regular July schedules (if any) retain their prior slots and status

#### Scenario: Delete one schedule does not delete sibling package schedules

- **WHEN** a verified admin deletes Premium Package’s July menu schedule
- **THEN** other packages’ July menu schedules continue to exist unchanged

### Requirement: Cross-package menu sync mutates only the explicit target

When a verified admin applies a cross-package menu sync suggestion, the system MUST apply assignment changes only to the explicitly selected target schedule. The source schedule and all non-target schedules for that cycle MUST remain unchanged by the apply operation.

#### Scenario: Apply sync updates only target package

- **WHEN** an admin applies sync from Regular July onto Student July
- **THEN** Student July assignments update per the sync rules and Regular July remains identical to its pre-apply state

### Requirement: Admin and customer reads are package-scoped for a month

List and retrieve APIs for monthly menus MUST identify schedules by package (meal category / plan) and cycle month together. The system MUST NOT expose or imply a single shared menu calendar for all packages in a month. Customer package-menu responses MUST include only the caller’s packages’ published schedules for the requested month without dropping another owned package’s menu when a different package is published.

#### Scenario: Two owned packages both return menus for the same month

- **WHEN** a verified customer has active orders for two different packages in July and both have published July schedules
- **THEN** the package-menu response includes both packages with their respective published day slots

#### Scenario: Publishing a second package does not empty the first in customer menu

- **WHEN** package A’s July menu was already visible to the customer and package B’s July menu is later published
- **THEN** package A’s July slots remain present and unchanged in subsequent package-menu responses
