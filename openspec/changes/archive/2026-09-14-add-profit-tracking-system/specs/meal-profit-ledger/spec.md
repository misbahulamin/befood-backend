## ADDED Requirements

### Requirement: Immutable profit ledger row per charged delivery
The system SHALL persist an immutable meal profit ledger record for each `OrderDelivery` that has been successfully charged (`payment_status=charged` with a linked meal-payment wallet debit). Each record MUST store at least: public id, customer reference, order delivery reference, meal package reference, meal period, service date, meal price (charged revenue), food cost (published ingredient cost snapshot at recognition), profit amount (published profit snapshot at recognition), profit percentage frozen at recognition, source, and created/recognized timestamps. After creation, financial snapshot fields MUST NOT change when later menu, ingredient, or package prices change.

#### Scenario: Successful charged delivery creates one profit record
- **WHEN** a delivery transitions to `delivered` and the customer wallet is successfully charged for that meal
- **THEN** exactly one profit ledger record exists for that delivery with meal price equal to the charged amount and profit amount equal to the published slot `profit_snapshot` (or `0.00` when the snapshot is missing)

#### Scenario: Later catalog price change does not alter stored profit
- **WHEN** admin later changes ingredient catalog costs or republishes a different margin after a profit record exists
- **THEN** the existing profit ledger financial fields remain unchanged

### Requirement: Profit is created only for successful charged deliveries
The system MUST NOT create a profit ledger record for Meal OFF / skipped deliveries, low-balance blocked deliveries that never become charged, missed deliveries, or failed charge attempts. Profit recognition MUST occur only after a successful meal-payment charge attach for that delivery.

#### Scenario: Meal OFF does not create profit
- **WHEN** a customer meal-offs a scheduled delivery (status becomes `skipped`) and no wallet debit occurs
- **THEN** no profit ledger record exists for that delivery

#### Scenario: Failed or blocked charge does not create profit
- **WHEN** mark-delivered is rejected due to insufficient or frozen wallet (or otherwise fails to charge)
- **THEN** the delivery is not charged and no profit ledger record is created

### Requirement: Profit recognition is idempotent per delivery
The system MUST ensure at most one profit ledger record exists per `OrderDelivery`. Retries of auto-delivery cron, repeated mark-delivered, or concurrent recognition attempts MUST NOT create duplicate profit rows or double-count revenue/profit.

#### Scenario: Retry after successful charge does not duplicate profit
- **WHEN** a delivery is already charged and already has a profit ledger record, and mark-delivered or recognition runs again
- **THEN** still exactly one profit ledger record exists for that delivery and aggregates are unchanged by the retry

#### Scenario: Concurrent recognition creates a single row
- **WHEN** two concurrent recognition attempts target the same newly charged delivery
- **THEN** exactly one profit ledger record is persisted

### Requirement: Recognition reuses published slot snapshot resolution
The system MUST resolve meal package and published slot using the same rules as existing meal payment / live profit helpers (`delivery_meal` and published slot resolution for service date + meal period). The system MUST NOT invent a separate live costing formula at recognition time. Food cost MUST come from the published slot `ingredient_cost_snapshot` when present; profit amount MUST come from `profit_snapshot` when present; missing snapshots MUST store `0.00` for the missing financial component consistently with prior live aggregation behavior.

#### Scenario: Lunch and dinner use their own slot snapshots
- **WHEN** lunch and dinner deliveries on the same package and date are both charged successfully with different slot profit snapshots
- **THEN** each delivery’s profit ledger row stores its own meal period’s snapshot-derived profit and food cost
