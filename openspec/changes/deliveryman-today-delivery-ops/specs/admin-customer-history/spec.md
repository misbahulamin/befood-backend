## ADDED Requirements

### Requirement: Meal delivered activity includes Delivery Man identity when known
When composing customer activity events of type `meal_delivered`, the system SHALL include the Delivery Man identity in the activity summary and refs when the underlying delivery has rider attribution (`delivered_by_rider` or equivalent). When attribution is missing, the event MAY omit rider fields but MUST still include delivery, meal period, service date, and package information as today.

#### Scenario: Activity shows who delivered
- **WHEN** a delivery with `delivered_by_rider` set is included in the customer activity feed
- **THEN** the `meal_delivered` item summary identifies the Delivery Man by display name (or documented identifier) and refs include the rider public id when available

#### Scenario: Activity without rider still works
- **WHEN** a delivered meal has no rider attribution stored
- **THEN** the activity feed still returns a `meal_delivered` item without failing, using the existing delivery/package refs
