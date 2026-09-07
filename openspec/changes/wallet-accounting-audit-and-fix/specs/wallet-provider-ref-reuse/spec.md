## ADDED Requirements

### Requirement: Provider transaction id reuse follows live-status uniqueness
The system SHALL treat a provider payment `transaction_id` (stored as wallet recharge `external_ref` for methods `bkash`, `nagad`, or `bank`) as taken only when another recharge row exists with the same `method` and `external_ref` and `status` in `pending` or `completed`. A prior recharge with the same ref in `failed` (admin-rejected) or `cancelled` MUST NOT block a new recharge request. Approving a recharge MUST continue to permanently block reuse of that ref while the completed row remains. Rejecting a recharge MUST set status to `failed`, MUST NOT credit customer or Admin Wallet balances, and MUST leave `external_ref` intact for audit.

#### Scenario: Rejected provider ref can be reused
- **WHEN** a customer creates a provider recharge with `transaction_id=TX002`, an admin rejects it (`status=failed`), and the customer submits a new recharge with the same method and `transaction_id=TX002`
- **THEN** the system accepts the new pending recharge request

#### Scenario: Pending provider ref cannot be reused
- **WHEN** a customer has a pending provider recharge with `transaction_id=TX001`
- **THEN** another recharge create with the same method and `transaction_id=TX001` is rejected as a duplicate

#### Scenario: Completed provider ref cannot be reused
- **WHEN** a provider recharge with `transaction_id=TX001` was approved (`status=completed`)
- **THEN** a new recharge create with the same method and `transaction_id=TX001` is rejected as a duplicate

#### Scenario: Rejected recharge does not move balances
- **WHEN** an admin rejects a pending provider recharge
- **THEN** the customer wallet balance and Admin Wallet balance are unchanged and the failed row retains its original `external_ref`

### Requirement: Database uniqueness matches live-status provider ref rule
The system MUST enforce uniqueness of `(method, external_ref)` for provider recharges at the database layer only for rows with `type=recharge`, provider methods (`bkash`/`nagad`/`bank`), non-empty `external_ref`, and `status` in `pending` or `completed`. The constraint MUST NOT prevent multiple historical `failed` rows from sharing a ref with a later live row. Existing approved (`completed`) recharge rows MUST NOT be rewritten by the uniqueness migration.

#### Scenario: Constraint allows failed then pending same ref
- **WHEN** a failed provider recharge already stores `external_ref=TX002` and a new pending recharge is inserted with the same method and ref
- **THEN** the insert succeeds under the live-status unique constraint

#### Scenario: Constraint still blocks two pending same refs
- **WHEN** two concurrent inserts attempt pending provider recharges with the same method and `external_ref`
- **THEN** at most one live pending/completed row is persisted and the other fails uniqueness
