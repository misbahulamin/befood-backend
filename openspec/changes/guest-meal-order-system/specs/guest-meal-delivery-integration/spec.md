## ADDED Requirements

### Requirement: Guest meals attach to existing delivery stops

The system SHALL represent guest meal fulfillment against the subscriber’s existing `OrderDelivery` for the same `service_date` and `meal_period` when that slot exists (or is ensured by the canonical subscription delivery generator). The system MUST NOT invent a parallel logistics status vocabulary for guest meals. Guest purchase records remain the financial source of truth; delivery rows remain the rider stop source of truth.

#### Scenario: Guest order links to subscription slot

- **WHEN** an active subscriber successfully creates a guest meal for a date and period that has a subscription `OrderDelivery`
- **THEN** the guest meal record references that delivery (or is aggregatable to it by customer, date, and period)

### Requirement: Rider and board visibility of guest quantity

Deliveryman and admin delivery boards that list meal stops for a service date and period MUST expose guest quantity for that stop when guest meals are due, so operators can deliver the correct number of boxes. Marking the parent delivery delivered MUST NOT trigger an additional wallet charge for already-prepaid guest meals.

#### Scenario: Board shows guest quantity

- **WHEN** a rider today-board includes a customer stop that has `2` countable guest meals for that slot
- **THEN** the stop payload includes guest quantity `2` (or equivalent documented field)

#### Scenario: Deliver does not re-charge guest meals

- **WHEN** an operator marks the parent `OrderDelivery` as delivered and guest meals for that slot were already prepaid
- **THEN** the regular meal charge-on-delivery path may run for the subscriber meal only and MUST NOT debit again for the guest meal totals

### Requirement: Guest fulfillment status follows delivery lifecycle without new enums

Guest meal operational status SHOULD reuse existing delivery outcomes (`scheduled`, `delivered`, `skipped`, `missed`) by mirroring or updating linked guest records when the parent stop transitions, without introducing unnecessary new status values. Cancellation/refund of guest meals remains out of scope until product confirms that decision.

#### Scenario: Parent delivered updates guest fulfillment

- **WHEN** the linked parent delivery becomes `delivered`
- **THEN** associated active guest meal records reflect a delivered (or equivalent documented) fulfillment state for ops/history
