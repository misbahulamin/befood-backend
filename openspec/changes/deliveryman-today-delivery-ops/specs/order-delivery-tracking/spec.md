## ADDED Requirements

### Requirement: Delivery Man mark delivered preserves durable delivery history and rider attribution
When a verified Delivery Man marks an in-zone `scheduled` `OrderDelivery` as `delivered`, the system SHALL update the existing delivery row to `delivered` (not delete it), SHALL record who marked it, SHALL persist rider attribution and completion timestamps using the existing logistics/mark fields when available (`marked_by`, `marked_at`, `delivered_by_rider`, `delivered_at`), and SHALL keep duplicate same-status marks idempotent or conflict-safe without double-charging.

#### Scenario: Deliveryman mark keeps row and attribution
- **WHEN** a verified Delivery Man successfully marks a scheduled zone delivery as delivered
- **THEN** the `OrderDelivery` row remains with status `delivered`, rider attribution is stored when resolvable, and a completion timestamp is stored

#### Scenario: Duplicate deliveryman mark is safe
- **WHEN** the same Delivery Man marks the same already-delivered stop as delivered again
- **THEN** the system MUST NOT create a second charge or corrupt status, and MUST return a stable success or conflict response consistent with existing mark semantics
