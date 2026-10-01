## ADDED Requirements

### Requirement: Prepaid guest meal debit is separate from charge-on-delivery

The system SHALL treat Guest Meal wallet charges as prepaid purchases at guest-meal create time. The existing rule that regular `OrderDelivery` meal charges occur only when status becomes `delivered` remains unchanged for the subscriber’s own meal slot. Guest meal debits MUST use the canonical wallet ledger with auditable metadata (purpose/type distinguishing guest meal from meal-delivery charge-on-delivery). Marking a delivery delivered MUST NOT create a second wallet debit for guest meal quantities already paid at create time.

#### Scenario: Guest create debits immediately

- **WHEN** a verified active subscriber successfully creates a guest meal order
- **THEN** a completed wallet debit for the guest meal total exists immediately and the regular delivery may still be `scheduled` without a meal-delivery charge

#### Scenario: Delivered regular meal does not re-charge guest total

- **WHEN** a delivery with linked prepaid guest meals is marked `delivered`
- **THEN** the meal-delivery charge path charges only the regular published slot meal amount for that delivery and MUST NOT debit the previously paid guest meal total again
