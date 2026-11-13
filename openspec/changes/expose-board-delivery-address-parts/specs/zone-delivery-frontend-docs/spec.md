# Spec Delta

## Purpose

Keeps deliveryman board frontend documentation aligned with the customer-row address fields so mobile and Admin clients know which keys to render for Building / Floor / Flat.

## ADDED Requirements

### Requirement: Docs list building floor flat on board customers
Deliveryman zone/board frontend documentation SHALL document that each today-board customer object includes `building_name`, `floor`, and `flat_number` alongside `full_address` (and existing area/city fields when documented). Docs MUST state that empty strings mean the part is unknown and MUST NOT imply clients should invent values.

#### Scenario: Engineer finds the three keys in docs
- **WHEN** an engineer reads the deliveryman today-board customer example in `delivery_zones/docs/frontend/zone-based-delivery.md` (or the linked today-ops board field list)
- **THEN** the documented customer shape MUST include `building_name`, `floor`, and `flat_number`
