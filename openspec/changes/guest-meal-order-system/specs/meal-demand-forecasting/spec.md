## ADDED Requirements

### Requirement: Kitchen demand includes guest meal quantities

For a given `service_date` and `meal_period`, meal demand calculations MUST include countable prepaid guest meal units that are still expected for cooking/delivery for that slot (in addition to existing live `OrderDelivery` row counts). Guest units MUST increase expected and final cooking counts when the guest meals are active for that slot, and MUST NOT double-count the subscriber’s regular delivery row. Low-balance blocking and meal-off exclusions for the regular delivery continue to apply to the regular unit per existing rules; guest-unit interaction with meal-off/low-balance MUST follow the guest-meal product rules documented for that change.

#### Scenario: Guest quantity increases cooking count

- **WHEN** one live non-skipped delivery exists for `(D, lunch)` and the same customer has `2` countable guest meals for that slot
- **THEN** demand expected/cooking counts for that package include the regular delivery unit plus `2` guest units as documented

#### Scenario: Cancelled or non-countable guest meals excluded

- **WHEN** guest meal records exist for `(D, dinner)` but are not in a countable/active fulfillment state
- **THEN** those quantities MUST NOT inflate final cooking count
