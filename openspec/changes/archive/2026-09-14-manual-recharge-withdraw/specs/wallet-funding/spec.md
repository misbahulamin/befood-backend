## MODIFIED Requirements

### Requirement: Customer can recharge wallet with manual funding
The system SHALL allow an authenticated verified customer to submit a wallet recharge request by posting a positive monetary `amount`, a supported `payment_method` of `bkash`, `nagad`, or `bank`, and a non-empty `transaction_id`. The system MUST resolve the customer from authentication and MUST NOT trust a client-supplied user id. The public API field `transaction_id` MUST be sanitized and stored on the ledger as `external_ref`. On success the system MUST create a ledger transaction with `type=recharge`, `direction=credit`, `status=pending`, `method` equal to the selected payment method, and MUST NOT increase the wallet balance at submit time. The system MUST reject with `400 Bad Request` non-positive amounts, amounts with more than two decimal places, amounts above the configured maximum, unsupported payment methods (including `manual`), and empty/whitespace-only transaction ids. When `WALLET_MANUAL_FUNDING_ENABLED` is false, new customer recharge submissions MUST be rejected with `403 Forbidden`. Payment destination instructions MAY be shown by the client and are not required from this API.

#### Scenario: Successful pending recharge request
- **WHEN** an authenticated verified customer with an active wallet posts a valid recharge amount, `payment_method=bkash`, and a non-empty `transaction_id` while manual funding is enabled
- **THEN** the system responds with success, a `recharge` transaction exists with `status=pending` and matching `method`/`external_ref`, and the wallet balance is unchanged

#### Scenario: Invalid recharge amount rejected
- **WHEN** a customer posts a recharge with amount `0`, a negative value, or more than two decimal places
- **THEN** the system responds `400 Bad Request` and does not create a completed credit or change the wallet balance

#### Scenario: Unsupported payment method rejected
- **WHEN** a customer posts a recharge with a payment method other than `bkash`, `nagad`, or `bank`
- **THEN** the system responds `400 Bad Request` and does not create a funding transaction

#### Scenario: Empty transaction id rejected
- **WHEN** a customer posts a recharge with a blank or whitespace-only `transaction_id`
- **THEN** the system responds `400 Bad Request` and does not create a funding transaction

#### Scenario: Amount above configured maximum rejected
- **WHEN** a customer posts a recharge amount above the configured funding maximum
- **THEN** the system responds `400 Bad Request` and does not create a funding transaction

#### Scenario: Kill switch blocks new recharge
- **WHEN** `WALLET_MANUAL_FUNDING_ENABLED` is false and a customer posts a recharge
- **THEN** the system responds `403 Forbidden` and does not create a funding transaction

#### Scenario: Frozen wallet cannot recharge
- **WHEN** a customer whose wallet `status` is `frozen` posts a recharge
- **THEN** the system rejects the operation with a client error and does not credit the balance

#### Scenario: Unauthenticated recharge rejected
- **WHEN** an unauthenticated client posts a recharge
- **THEN** the system responds `401 Unauthorized`

### Requirement: Customer can withdraw from wallet with manual debit
The system SHALL allow an authenticated verified customer to submit a withdraw request by posting a positive monetary `amount` that passes shared amount validation (positive, max two decimal places, within the configured funding/transaction maximum) and does not exceed the current spendable `Wallet.balance`. On success the system MUST create a ledger transaction with `type=withdraw`, `direction=debit`, `status=pending`, `method=manual`, and empty `external_ref`, and MUST immediately decrease `Wallet.balance` by that amount so the funds cannot be spent elsewhere while the request is pending. The customer withdraw API MUST NOT require a provider `transaction_id` in this release. The system MUST NOT mark the withdraw `completed` and MUST NOT debit Admin Wallet custody at submit time. Insufficient spendable balance MUST return `400 Bad Request` without changing the balance. Amounts above the configured maximum MUST return `400 Bad Request`. Frozen wallets MUST reject new withdraw submissions. When `WALLET_MANUAL_FUNDING_ENABLED` is false, new customer withdraw submissions MUST be rejected with `403 Forbidden`.

#### Scenario: Successful pending withdraw reserves balance
- **WHEN** an authenticated verified customer with balance at least `500.00` posts a withdraw of `500.00` while manual funding is enabled
- **THEN** the system responds with success, a `withdraw` transaction exists with `status=pending` and `method=manual`, and the wallet balance decreases by `500.00`

#### Scenario: Withdraw exceeds balance
- **WHEN** a customer posts a withdraw amount greater than the current spendable balance
- **THEN** the system responds `400 Bad Request` and the balance remains unchanged

#### Scenario: Withdraw above configured maximum rejected
- **WHEN** a customer posts a withdraw amount above the configured funding maximum even if balance is sufficient
- **THEN** the system responds `400 Bad Request` and the balance remains unchanged

#### Scenario: Second withdraw cannot spend reserved funds
- **WHEN** a customer has a pending withdraw that already reduced balance and then posts another withdraw greater than the remaining balance
- **THEN** the system responds `400 Bad Request` for insufficient funds

#### Scenario: Kill switch blocks new withdraw
- **WHEN** `WALLET_MANUAL_FUNDING_ENABLED` is false and a customer posts a withdraw
- **THEN** the system responds `403 Forbidden` and does not create a funding transaction

#### Scenario: Frozen wallet cannot withdraw
- **WHEN** a customer whose wallet `status` is `frozen` posts a withdraw
- **THEN** the system rejects the operation and does not debit the balance

### Requirement: Funding operations support idempotent retries
The system SHALL accept an optional idempotency key on recharge and withdraw. Idempotency lookup MUST occur after payload normalization and **before** duplicate provider-ref validation and before spendable-balance validation that may already reflect the original request. Lookup MUST be by `wallet + idempotency_key` only and MUST NOT use funding type as part of the lookup namespace (matching the per-wallet unique `idempotency_key` constraint). When a row is found, the system MUST compare the effective funding fingerprint. When the fingerprint matches, the system MUST return that existing funding transaction using its **current persisted status** (`pending`, `completed`, or `failed`) without creating another row, reserving balance again, changing balance/custody, releasing a reservation, or sending another admin notification. When the fingerprint conflicts — including reuse of the same key for a different type (recharge vs withdraw) or different amount/method/ref — the system MUST respond `409 Conflict`. The effective fingerprint MUST include transaction type (`recharge`/`withdraw`), normalized amount, and for recharge also payment method and sanitized transaction id/`external_ref`. The optional `note` field MUST NOT participate in the fingerprint. Concurrent requests with the same idempotency key MUST create or apply funding effects only once (DB uniqueness and/or row locking).

#### Scenario: Replay same recharge idempotency key returns original
- **WHEN** a customer successfully submits a recharge with an idempotency key and then retries the same key with the same amount, method, and transaction id while the row is still pending
- **THEN** the system returns the original pending transaction and does not create a second pending recharge

#### Scenario: Replay after admin approval returns current completed status
- **WHEN** a customer creates a recharge with an idempotency key, an admin later approves it to `completed`, and the customer retries the same key with the same fingerprint
- **THEN** the system returns the same `public_id` with `status=completed`, creates no new row, sends no new admin email, and applies no additional balance or custody change

#### Scenario: Replay after admin rejection returns current failed status
- **WHEN** a customer creates a recharge with an idempotency key, an admin later rejects it to `failed`, and the customer retries the same key with the same fingerprint
- **THEN** the system returns the same `public_id` with `status=failed` and creates no new row or side effects

#### Scenario: Replay same withdraw idempotency key after reservation
- **WHEN** a customer successfully submits a withdraw with an idempotency key that reserved balance and then retries the same key with the same amount
- **THEN** the system returns the original withdraw transaction with its current persisted status and does not attempt a second reservation or return insufficient funds solely due to the already-reserved amount

#### Scenario: Same key reused across recharge and withdraw conflicts
- **WHEN** a customer has used an idempotency key for a recharge and later submits a withdraw with the same key
- **THEN** the system responds `409 Conflict` and does not create a withdraw row for that key

#### Scenario: Idempotency key reused with conflicting payload
- **WHEN** a customer reuses an idempotency key for a funding request with a different amount, recharge method, or recharge transaction id
- **THEN** the system responds `409 Conflict` and does not apply an additional balance or pending-row change

#### Scenario: Concurrent same-key submissions apply once
- **WHEN** two concurrent funding submissions use the same idempotency key and same effective payload for the same customer wallet
- **THEN** only one funding transaction is created/applied for that key

### Requirement: Funding model is gateway-ready without live gateway integration
The system SHALL persist `method` and `status` on funding transactions so off-platform manual verification and future live gateways can share the same ledger. This release MUST NOT claim a live gateway payment succeeded and MUST NOT require gateway credentials. Allowed customer-selected recharge methods MUST include `bkash`, `nagad`, and `bank`. Customer withdraw requests in this release MUST store `method=manual`. Method value `manual` MUST NOT be accepted as a customer recharge payment method.

#### Scenario: Manual verification path creates pending without gateway call
- **WHEN** a customer submits recharge or withdraw in this release
- **THEN** the transaction is stored with the release-defined method and `status=pending` without calling an external payment provider API

#### Scenario: Schema allows bank alongside bKash and Nagad
- **WHEN** wallet funding transactions are stored for customer recharge
- **THEN** the `method` field allows `bkash`, `nagad`, and `bank`

#### Scenario: Withdraw stores manual method
- **WHEN** a customer successfully submits a withdraw request
- **THEN** the ledger row has `method=manual` and empty `external_ref`

### Requirement: Successful recharge syncs Admin Wallet custody
When a customer recharge is approved and becomes completed, the system MUST also credit the platform Admin Wallet custody ledger for the same amount (idempotent per customer wallet transaction), subject to the Admin Wallet funding-custody feature flag when present. Creating a pending recharge MUST NOT credit Admin Wallet custody. Customer-facing recharge submit responses remain request identity and pending status; Admin Wallet details are not required in the customer response.

#### Scenario: Pending recharge does not credit Admin Wallet
- **WHEN** a verified customer successfully submits a pending recharge of `500.00`
- **THEN** the customer wallet balance is unchanged and no Admin Wallet `customer_funding` credit is created yet

#### Scenario: Approved recharge credits customer wallet and Admin Wallet together
- **WHEN** a verified admin approves a pending recharge of `500.00`
- **THEN** the customer wallet balance increases by `500.00` and the Admin Wallet receives a matching custody credit for that recharge transaction

#### Scenario: Second approve does not double-credit either ledger
- **WHEN** a pending recharge is approved successfully and a second approve is attempted
- **THEN** the system responds `409 Conflict` and neither the customer wallet nor the Admin Wallet applies a second credit for that event

### Requirement: Successful withdraw syncs Admin Wallet custody
When a customer withdraw is approved and becomes completed, the system MUST also debit the platform Admin Wallet custody ledger for the same amount (idempotent per customer wallet transaction). Creating a pending withdraw MUST NOT debit Admin Wallet custody. If Admin Wallet custody cannot cover the debit at approve time, the system MUST respond `409 Conflict`, MUST leave the withdraw `pending`, MUST leave the customer reservation in place, MUST create no Admin Wallet debit, and MUST leave `reviewed_by`, `reviewed_at`, and `rejection_reason` unchanged. Rejecting a pending withdraw MUST restore the reserved customer balance and MUST NOT debit Admin Wallet custody.

#### Scenario: Pending withdraw does not debit Admin Wallet
- **WHEN** a verified customer successfully submits a pending withdraw of `100.00`
- **THEN** the customer spendable balance decreases by `100.00` and no Admin Wallet `customer_withdraw` debit is created yet

#### Scenario: Approved withdraw finalizes custody debit
- **WHEN** a verified admin approves a pending withdraw of `100.00` and Admin Wallet float is sufficient
- **THEN** the withdraw becomes `completed` and the Admin Wallet receives a matching custody debit for that withdraw transaction

#### Scenario: Admin Wallet float shortfall is fully non-mutating
- **WHEN** an admin attempts to approve a pending withdraw that exceeds Admin Wallet balance
- **THEN** the system responds `409 Conflict`, the withdraw remains `pending`, the customer reserved balance stays reduced, no Admin Wallet debit is created, and review audit fields remain unchanged

## ADDED Requirements

### Requirement: Duplicate recharge provider transaction ids are rejected
The system SHALL reject a recharge request when the same non-empty `(method, external_ref)` pair already exists on a **provider-method recharge** wallet transaction (`method` in `bkash`, `nagad`, `bank`). Matching MUST use the sanitized `transaction_id` stored as `external_ref`. The system MUST enforce a database partial unique constraint scoped to those recharge provider-method rows with non-empty `external_ref`, in addition to service validation. Historical/internal `manual` recharge refs MUST NOT be required to participate in this uniqueness set. Uniqueness MUST NOT be applied globally to all wallet transaction types solely by `(method, external_ref)`. Concurrent duplicate provider recharge submissions MUST result in only one stored recharge row for that provider ref.

#### Scenario: Duplicate method and transaction id rejected
- **WHEN** a customer submits a recharge with `payment_method=bkash` and `transaction_id=TX123` and another provider-method recharge already exists with the same method and external_ref
- **THEN** the system responds `409 Conflict` and does not create another pending recharge

#### Scenario: Concurrent duplicate transaction id submissions
- **WHEN** two concurrent recharge submissions use the same sanitized provider `payment_method` and `transaction_id`
- **THEN** only one recharge funding transaction is persisted for that provider reference

### Requirement: Customer can view own recharge and withdraw request history
The system SHALL allow an authenticated verified customer to list and retrieve their own wallet transactions, including pending, completed, and failed recharge/withdraw funding rows, using existing ownership rules (`public_id`, caller wallet only). Customer-visible funding fields MAY include `public_id`, `type`, `direction`, `amount`, `status`, `method`, transaction id where relevant, `created_at`, `reviewed_at`, and `rejection_reason`. Customer responses MUST NOT expose reviewer identity, email, or admin profile information. Another customer’s funding requests MUST NOT be accessible (`404 Not Found`).

#### Scenario: Customer sees own pending recharge in history
- **WHEN** an authenticated verified customer lists wallet transactions after submitting a pending recharge
- **THEN** the pending recharge appears in that customer’s history with `status=pending`

#### Scenario: Customer history omits reviewer identity
- **WHEN** an authenticated verified customer retrieves an approved or rejected funding transaction
- **THEN** the response does not include the approving/rejecting admin’s identity or email

#### Scenario: Foreign funding request not found
- **WHEN** an authenticated verified customer requests another customer’s funding transaction `public_id`
- **THEN** the system responds `404 Not Found`

### Requirement: Funding create validates after idempotency resolution
For new funding creates (no matching idempotent result), the system MUST apply normal validation only after idempotency resolution, including amount rules, recharge method/transaction id rules, recharge duplicate-ref checks, and withdraw spendable-balance checks, then perform the ledger mutation atomically.

#### Scenario: Idempotent replay skips duplicate-ref failure path
- **WHEN** a customer replays the same recharge idempotency key and payload after the original row already holds that provider transaction id
- **THEN** the system returns the existing transaction with its current persisted status instead of `409` duplicate transaction id

### Requirement: Kill switch does not block admin resolution of existing pending funding
Disabling `WALLET_MANUAL_FUNDING_ENABLED` MUST NOT prevent verified admins from listing, retrieving, approving, or rejecting funding requests that were already pending before the flag was disabled.

#### Scenario: Admin resolves pending withdraw after kill switch disabled
- **WHEN** a pending withdraw was created while funding was enabled and then `WALLET_MANUAL_FUNDING_ENABLED` is set false
- **THEN** a verified admin can still approve or reject that pending withdraw
