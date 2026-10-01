## ADDED Requirements

### Requirement: Admin customer detail offers cancel with confirmation

The admin Customer Detail experience MUST allow a verified admin to cancel the customer’s active subscription from the Active Subscription section. Activating cancel MUST open a confirmation modal (reusing existing admin modal patterns) and MUST NOT cancel on a single accidental click. The modal MUST state that meals still inside the meal-off window will be cancelled, while past-cutoff meals remain scheduled and may still be charged from the wallet.

#### Scenario: Cancel button only for active subscription and verified admin

- **WHEN** the customer has an active subscription and the signed-in admin is verified
- **THEN** a Cancel Subscription control is available on the Active Subscription UI

#### Scenario: No cancel control without active subscription

- **WHEN** the customer has no active subscription
- **THEN** the Cancel Subscription control is not offered

#### Scenario: Confirmation required

- **WHEN** the admin clicks Cancel Subscription
- **THEN** a confirmation modal is shown and no cancel API call runs until the admin confirms

### Requirement: Impact numbers come from backend preview or cancel response

The admin UI MUST load cancel impact details (meals to cancel, preserved finalized meals, estimated liability, withdrawable balance) from the backend preview and/or cancel response. The UI MUST NOT locally compute meal liability or withdrawable balance from raw balance and threshold/price arithmetic.

#### Scenario: Modal shows backend preview data

- **WHEN** the confirmation modal opens successfully
- **THEN** it displays cancelled vs preserved meal information and wallet figures supplied by the backend preview

### Requirement: Successful cancel refreshes customer 360 data

After a successful admin cancel mutation, the admin UI MUST invalidate or refetch customer overview, active subscription, subscription history, meals, wallet overview, and activity (and admin subscription caches when applicable) so the page shows cancelled status without a full manual reload. Success and failure MUST use the project’s existing toast/error mapping patterns.

#### Scenario: After cancel active tab updates

- **WHEN** admin confirm cancel succeeds
- **THEN** the Active Subscription view reflects no active subscription (or cancelled state) and a success notification is shown

#### Scenario: Cancel API error surfaces to admin

- **WHEN** the cancel API returns an error
- **THEN** the modal or page shows a mapped error toast/message and the subscription remains unchanged in the UI until a successful refetch
