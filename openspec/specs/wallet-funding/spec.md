## Purpose

Customer wallet recharge and withdraw with validated amounts, optional idempotency, a manual funding path, and distinct meal-delivery payment debits.
## Requirements
### Requirement: Customer can recharge wallet with manual funding
The system SHALL allow an authenticated verified customer to recharge their wallet by posting a positive monetary `amount`. For this release, successful recharge MUST credit the wallet immediately, create a completed ledger transaction with `type=recharge`, `direction=credit`, and `method=manual`, and return the updated wallet balance together with the transaction `public_id`. The system MUST reject non-positive amounts, amounts with more than two decimal places, and amounts above the configured maximum. The customer MUST NOT supply a payment gateway method in this release; the server sets `manual`.

#### Scenario: Successful manual recharge
- **WHEN** an authenticated verified customer with an active wallet posts a valid recharge amount (for example `500.00`)
- **THEN** the system responds with success, the wallet balance increases by that amount, and a completed `recharge` transaction with `method=manual` exists

#### Scenario: Invalid recharge amount rejected
- **WHEN** a customer posts a recharge with amount `0`, a negative value, or more than two decimal places
- **THEN** the system responds `400` or `422` and does not change the wallet balance

#### Scenario: Frozen wallet cannot recharge
- **WHEN** a customer whose wallet `status` is `frozen` posts a recharge
- **THEN** the system rejects the operation and does not credit the balance

#### Scenario: Unauthenticated recharge rejected
- **WHEN** an unauthenticated client posts a recharge
- **THEN** the system responds `401 Unauthorized`

### Requirement: Customer can withdraw from wallet with manual debit
The system SHALL allow an authenticated verified customer to withdraw by posting a positive monetary `amount` not exceeding the current balance. For this release, successful withdraw MUST debit the wallet immediately, create a completed ledger transaction with `type=withdraw`, `direction=debit`, and `method=manual`, and return the updated balance together with the transaction `public_id`. Insufficient funds MUST be rejected without changing the balance. Frozen wallets MUST reject withdraw.

#### Scenario: Successful manual withdraw
- **WHEN** an authenticated verified customer with balance at least `500.00` posts a withdraw of `500.00`
- **THEN** the system responds with success, the wallet balance decreases by `500.00`, and a completed `withdraw` transaction with `method=manual` exists

#### Scenario: Withdraw exceeds balance
- **WHEN** a customer posts a withdraw amount greater than the current balance
- **THEN** the system rejects the operation and the balance remains unchanged

#### Scenario: Frozen wallet cannot withdraw
- **WHEN** a customer whose wallet `status` is `frozen` posts a withdraw
- **THEN** the system rejects the operation and does not debit the balance

### Requirement: Funding operations support idempotent retries
The system SHALL accept an optional idempotency key on recharge and withdraw. When the same customer reuses the same key with the same effective funding request, the system MUST return the original successful result without applying the balance change twice. When the same key is reused with a different amount, the system MUST respond `409 Conflict`.

#### Scenario: Replay same idempotency key does not double credit
- **WHEN** a customer successfully recharges with an idempotency key and then retries the same recharge with the same key and amount
- **THEN** the system returns the original transaction outcome and the wallet is credited only once

#### Scenario: Idempotency key reused with different amount
- **WHEN** a customer reuses an idempotency key for a funding request with a different amount
- **THEN** the system responds `409 Conflict` and does not apply an additional balance change

### Requirement: Funding model is gateway-ready without live gateway integration
The system SHALL persist `method` and `status` on funding transactions so future bKash/Nagad (and similar) flows can create pending transactions and complete them after provider confirmation. This release MUST NOT claim a live gateway payment succeeded and MUST NOT require gateway credentials. Reserved method values MUST include at least `manual`, `bkash`, and `nagad`.

#### Scenario: Manual path completes without gateway
- **WHEN** a customer completes recharge or withdraw in this release
- **THEN** the transaction `method` is `manual` and `status` is `completed` without calling an external payment provider

#### Scenario: Schema reserves gateway methods
- **WHEN** wallet funding transactions are stored
- **THEN** the `method` field allows `bkash` and `nagad` as reserved values for future integration even though customer APIs do not select them yet

### Requirement: Payment type is used for meal-delivery wallet charges

The system SHALL record successful meal-delivery wallet charges as ledger transactions with `type=payment` and `direction=debit`, distinct from customer-initiated `withdraw` funding debits and from `recharge` credits. Order create and wallet minimum-balance eligibility checks MUST continue to avoid creating payment debits. Manual recharge and withdraw funding rules from this capability remain unchanged.

#### Scenario: Delivered meal creates payment debit not withdraw

- **WHEN** a delivery is successfully marked `delivered` and the wallet is charged
- **THEN** the ledger row has `type=payment` and `direction=debit`, not `type=withdraw`

#### Scenario: Order create still does not create payment debit

- **WHEN** a verified customer creates a meal package order with sufficient minimum wallet balance
- **THEN** the system does not create a `type=payment` debit solely due to order creation

### Requirement: Successful recharge syncs Admin Wallet custody
When a customer manual recharge completes successfully, the system MUST also credit the platform Admin Wallet custody ledger for the same amount (idempotent per customer wallet transaction), subject to the Admin Wallet funding-custody feature flag when present. Customer-facing recharge response fields remain the wallet balance and transaction identity; Admin Wallet details are not required in the customer response.

#### Scenario: Recharge credits customer wallet and Admin Wallet together
- **WHEN** a verified customer successfully recharges `500.00`
- **THEN** the customer wallet balance increases by `500.00` and the Admin Wallet receives a matching custody credit for that recharge transaction

#### Scenario: Idempotent recharge does not double-credit either ledger
- **WHEN** the same recharge idempotency key and amount are replayed after success
- **THEN** neither the customer wallet nor the Admin Wallet applies a second credit for that event

### Requirement: Successful withdraw syncs Admin Wallet custody
When a customer manual withdraw completes successfully, the system MUST also debit the platform Admin Wallet custody ledger for the same amount (idempotent per customer wallet transaction). If Admin Wallet custody cannot cover the debit, the system MUST reject the withdraw without changing the customer wallet balance.

#### Scenario: Withdraw debits customer wallet and Admin Wallet together
- **WHEN** a verified customer successfully withdraws `100.00` and Admin Wallet float is sufficient
- **THEN** the customer wallet balance decreases by `100.00` and the Admin Wallet receives a matching custody debit for that withdraw transaction

#### Scenario: Admin Wallet float shortfall rejects withdraw
- **WHEN** a customer requests a withdraw that exceeds Admin Wallet balance
- **THEN** the system rejects the withdraw and the customer wallet balance is unchanged

### Requirement: Customer funding permission uses unified identity verification
The system SHALL treat a customer as permitted for manual wallet funding (recharge and withdraw submit) when `is_customer_identity_verified` (or equivalent) is true—including when trust comes only from phone verification. The system MUST NOT require email verification for phone-registered customers to submit funding requests. Unauthenticated callers MUST still receive `401`. Callers with no trusted identity factor MUST receive `403` for identity denial (distinct from funding kill-switch or frozen-wallet denials).

#### Scenario: Phone-verified customer may submit manual recharge
- **WHEN** an authenticated phone-verified customer with unverified email submits a valid manual recharge request
- **THEN** the system does not deny the request for email verification and applies the existing manual funding create rules

#### Scenario: Phone-verified customer may submit manual withdraw
- **WHEN** an authenticated phone-verified customer with unverified email submits a valid manual withdraw request
- **THEN** the system does not deny the request for email verification and applies the existing manual funding withdraw rules

#### Scenario: No trusted identity cannot submit funding
- **WHEN** an authenticated customer with no email, phone, or social identity verification submits recharge or withdraw
- **THEN** the system responds `403` for identity verification failure before creating a funding transaction

### Requirement: Provider recharge duplicate checks ignore failed refs
When creating a customer provider recharge request (`bkash`/`nagad`/`bank` with non-empty `transaction_id`), the funding service MUST reject the request as a duplicate only if a matching recharge `external_ref` already exists in `pending` or `completed` status. Failed or cancelled prior requests with the same provider ref MUST be ignored for duplicate detection. Manual recharge flows without provider refs remain unchanged. Admin approve/reject endpoints, notification scheduling, and Admin Wallet custody sync on approve MUST remain behaviorally unchanged except for this uniqueness rule.

#### Scenario: Reuse after reject succeeds
- **WHEN** the only prior row for method `bkash` and `external_ref=TX12345` is `status=failed`
- **THEN** `request_recharge` creates a new pending recharge for that ref

#### Scenario: Duplicate of approved recharge still fails
- **WHEN** a completed `bkash` recharge already exists with `external_ref=TX12345`
- **THEN** `request_recharge` with the same method and transaction id raises the existing duplicate-provider-ref error without creating a new row

### Requirement: Admin funding request list supports people search

The verified-admin wallet funding request collection MUST accept an allowlisted query parameter `q` that filters requests by the related customer's people-search fields (name, email, username, phone with shared normalization, and exact customer `public_id` when `q` is a canonical UUID). Filtering MUST use `build_customer_people_q` with a queryset-relative `customer_prefix` for the funding request's customer relation. OpenAPI for the list operation MUST document `q`. Invalid unrelated filters remain subject to existing allowlist/`400` rules where enforced.

#### Scenario: Admin searches funding requests by customer email fragment

- **WHEN** a verified admin lists funding requests with `q` matching part of a related customer's email
- **THEN** only funding requests for matching customers are returned

#### Scenario: Admin searches funding requests by customer public_id

- **WHEN** a verified admin lists funding requests with `q` equal to a related customer's canonical `public_id`
- **THEN** funding requests for that customer are included

#### Scenario: Empty q does not restrict results

- **WHEN** a verified admin lists funding requests without `q` or with blank `q`
- **THEN** people-search does not further restrict the queryset beyond other applied filters

### Requirement: Approved pending recharge schedules customer confirmation
When a verified admin successfully approves a pending customer recharge and the wallet credit is committed, the system SHALL schedule customer confirmation side effects (mobile push notification and professional invoice email) after commit without changing the existing credit amount, `completed` status semantics, review fields, or Admin Wallet custody sync rules for that approval. Failure of those side effects MUST NOT reverse the credit or custody movement.

#### Scenario: Successful approve still credits once and notifies after commit
- **WHEN** a verified admin approves a pending recharge of `500.00`
- **THEN** the customer wallet increases by `500.00` exactly once, the transaction is `completed`, Admin Wallet custody sync rules for that recharge still apply, and after commit the system attempts customer push and invoice email side effects

#### Scenario: Notification failure does not undo custody or credit
- **WHEN** post-commit customer notification sending fails after a successful approve
- **THEN** the customer wallet credit and Admin Wallet custody outcome for that approve remain intact

