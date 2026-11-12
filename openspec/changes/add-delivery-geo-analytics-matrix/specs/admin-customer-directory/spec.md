# Spec Delta

## ADDED Requirements

### Requirement: Customer list geo filters support analytics drill-down
The system SHALL keep allowlisted customer-list filters `zone_public_id`, `location_public_id`, `sub_location_public_id`, and `has_delivery_sub_location` available to verified admins so geo analytics matrix rows can deep-link into `/api/v1/web/customers/` without ad-hoc search. Unknown filter keys MUST still yield `400`.

#### Scenario: Drill-down by sub-location
- **WHEN** a verified admin lists customers with `sub_location_public_id` for a matrix row’s sub-location
- **THEN** only customers assigned to that sub-location are returned

#### Scenario: Drill-down unassigned customers
- **WHEN** a verified admin lists customers with `has_delivery_sub_location=false`
- **THEN** only customers without a delivery sub-location are returned
