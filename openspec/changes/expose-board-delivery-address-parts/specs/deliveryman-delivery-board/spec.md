# Spec Delta

## Purpose

Defines the deliveryman today-board customer-row address contract so riders receive street address plus Building / Floor / Flat parts that Admin already stores on delivery places.

## ADDED Requirements

### Requirement: Board customer rows include building floor flat
Each customer object on `GET /user_management/deliveryman/deliveries/today-board/` SHALL include additive string fields `building_name`, `floor`, and `flat_number`. When the linked delivery place (or equivalent address source used for that delivery) has those values, the fields MUST carry them. When absent, each field MUST be an empty string (or equivalent empty cue), not omitted in a way that breaks clients expecting the keys. Existing `full_address`, `area`, and `city` MUST remain unchanged.

#### Scenario: Place with structured parts appears on board
- **WHEN** a zone rider requests the today-board and a listed delivery’s place has building `Me likely hostel`, floor `5`, and flat `619`
- **THEN** that customer row MUST include `building_name` `Me likely hostel`, `floor` `5`, and `flat_number` `619` in addition to the existing `full_address`

#### Scenario: Missing structured parts stay empty
- **WHEN** a listed delivery has `full_address` but no building, floor, or flat on its address source
- **THEN** the customer row MUST still include `building_name`, `floor`, and `flat_number` as empty values and MUST NOT invent values

#### Scenario: Existing street fields unchanged
- **WHEN** a customer row is returned on the today-board
- **THEN** `full_address`, `area`, and `city` MUST continue to reflect the same snapshot/source semantics as before this change
