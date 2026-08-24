## REMOVED Requirements

### Requirement: Order create requires minimum wallet balance

**Reason:** The gated action is subscribe, not monthly order create.
**Migration:** Apply the same minimum-balance check (no debit) in `subscription-wallet-eligibility` before creating a `CustomerSubscription`.

### Requirement: Frozen wallet cannot place an order

**Reason:** Frozen wallets must fail subscribe, not order create.
**Migration:** Reject subscribe when wallet `status=frozen` per `subscription-wallet-eligibility`.

### Requirement: Month lock is evaluated before wallet balance

**Reason:** Month lock is removed; exclusivity is one active subscription.
**Migration:** Evaluate already-subscribed before the wallet check as specified in `subscription-wallet-eligibility`.
