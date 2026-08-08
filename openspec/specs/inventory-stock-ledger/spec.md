## Purpose

Append-only inventory stock ledger: quantity movements with before/after balances, negative-stock rejection, reconcilable on-hand, weighted average cost valuation, and allowlisted unit conversion.

## Requirements

### Requirement: Append-only inventory stock ledger
The system SHALL record every stock change as an append-only inventory stock movement with type, signed quantity delta in the item’s stock unit, quantity before, quantity after, acting admin when applicable, timestamps, and a reference to the originating purchase, usage, wastage, adjustment, or reversal record. Completed movement quantity fields MUST NOT be editable via API. The item’s denormalized on-hand quantity MUST be updated only inside the same atomic transaction that writes the movement.

#### Scenario: Purchase movement increases stock
- **WHEN** a confirmed purchase receives `50` kg of Beef and prior on-hand was `5` kg
- **THEN** a purchase movement of `+50` exists, quantity after is `55`, and on-hand becomes `55`

#### Scenario: Kitchen usage movement decreases stock
- **WHEN** kitchen usage issues `12` kg of Beef from on-hand `55` kg
- **THEN** a kitchen usage movement of `-12` exists and on-hand becomes `43`

### Requirement: Negative stock is rejected
The system MUST reject any outbound stock movement (kitchen usage, wastage, or negative adjustment) that would make on-hand quantity negative. The error MUST include a client-safe message that states available stock and unit, and MUST use a stable machine-readable error code such as `INSUFFICIENT_STOCK`. No partial movement MUST be persisted when the request is rejected.

#### Scenario: Issue above available stock fails
- **WHEN** available Beef is `10` kg and an admin attempts to issue `15` kg
- **THEN** the system rejects the transaction, creates no stock movement, and leaves on-hand at `10` kg

### Requirement: Stock is reconcilable from ledger
The system SHALL ensure that for each item, on-hand quantity equals the sum of all movement quantity deltas (from a documented opening of zero for new items). A reconcile helper or admin check MUST be able to detect drift between denormalized on-hand and ledger sum.

#### Scenario: Ledger sum matches on-hand
- **WHEN** an item has movements `+50`, `-12`, `-3`, `+2` and no other movements
- **THEN** on-hand quantity equals `37` and matches the ledger sum

### Requirement: Weighted average cost and valuation
The system SHALL maintain a weighted average unit cost per inventory item in the item’s default unit. When a purchase receives quantity `q` at unit cost `c` into prior on-hand `Q` at average cost `A`, the system MUST set the new average to `(Q*A + q*c) / (Q+q)` using decimal arithmetic. Kitchen usage and wastage MUST reduce on-hand quantity without changing average unit cost. Current inventory value for an item MUST be computed as `on-hand × average_unit_cost` (or zero when on-hand is zero). Monetary fields MUST NOT use binary floating-point types.

#### Scenario: WAC after two purchases
- **WHEN** Beef starts empty, then receives `10` kg at `500` BDT/kg and later `20` kg at `550` BDT/kg
- **THEN** average unit cost becomes `533.33` BDT/kg within documented decimal rounding and on-hand is `30` kg

#### Scenario: Usage does not change WAC
- **WHEN** Beef on-hand is `30` kg at average `533.33` and `5` kg is issued for kitchen use
- **THEN** on-hand becomes `25` kg and average unit cost remains unchanged

### Requirement: Unit conversion consistency for stock writes
When a stock write uses a unit different from the item default, the system MUST convert only allowlisted compatible pairs (`g`↔`kg`, `ml`↔`l` with factor `1000`) into the item’s default unit before ledgering. Incompatible units MUST be rejected. Stock on-hand and movements MUST be stored in the item default unit.

#### Scenario: Gram purchase converts to kg
- **WHEN** an item default unit is `kg` and a purchase line is entered as `500` `g`
- **THEN** the ledger posts `0.5` kg (within documented precision)

#### Scenario: Incompatible unit rejected
- **WHEN** an item default unit is `kg` and a usage request uses unit `piece`
- **THEN** the system rejects the request without changing stock
