## ADDED Requirements

### Requirement: Frontend contract documents To Deliver and Delivered tabs
The system SHALL publish frontend/API documentation describing how BeFood Express mobile should call pending vs delivered today lists (default board vs documented delivered status filter), including auth headers, example responses, and empty states.

#### Scenario: Docs cover both tabs
- **WHEN** a mobile engineer reads the deliveryman today-ops frontend doc
- **THEN** the doc explains which request returns To Deliver items and which returns Delivered items, with sample JSON

### Requirement: Frontend contract documents today summary and package breakdown
The documentation MUST describe the today-summary endpoint (or documented equivalent), field meanings for total/delivered/pending, package breakdown array shape, stop-count semantics, and timezone notes (Asia/Dhaka / meal-off).

#### Scenario: Docs explain package breakdown
- **WHEN** a mobile engineer implements the package breakdown UI
- **THEN** the doc shows example `packages` entries with `package_public_id`, `package_name`, and `count` and states that names are dynamic

### Requirement: Frontend contract documents package display fields and backward compatibility
The documentation MUST state that existing fields (`meal_name`, `menu_items_label`, `status`) remain for current app versions, recommend preferring `package_name` + `menu_items_label` for package/meal item display, and note that translating `status=scheduled` to “Assigned/নির্ধারিত” is a UI choice that can be de-emphasized without a backend status rename.

#### Scenario: Docs warn against removing old fields
- **WHEN** a client still depends on `meal_name` and `status`
- **THEN** the doc states those fields remain supported and new fields are additive
