## ADDED Requirements

### Requirement: Admin Delivery Man list may include zone and delivery KPI summaries
The system SHALL allow the verified-admin Delivery Man list (existing admin deliverymen directory and/or the analytics list) to expose assigned zone summary (nullable), `is_available` (or equivalent), joining/created timestamp, and optional today/month/lifetime completed-delivery counts when those analytics fields are enabled for the response serializer. Existing pending-queue filters and approval fields MUST continue to work.

#### Scenario: Approved rider list shows assigned zone
- **WHEN** a verified admin lists Delivery Men including an approved rider assigned to a zone
- **THEN** the list item includes that zone’s identifying summary (for example name or code) when zone assignment exists

#### Scenario: Pending queue behavior unchanged
- **WHEN** a verified admin requests the default pending Delivery Man queue
- **THEN** only email-verified pending profiles are returned as before

### Requirement: Admin Delivery Man detail includes operational overview fields
The system SHALL include on Delivery Man detail (approval/review detail and/or analytics overview): assigned zone, availability, joining date, and verification/approval status fields needed for an admin overview card. Detail MUST remain retrievable by `public_id`.

#### Scenario: Detail includes zone and availability
- **WHEN** a verified admin retrieves a Delivery Man who is zone-assigned and marked available
- **THEN** the response includes assigned zone information and availability true
