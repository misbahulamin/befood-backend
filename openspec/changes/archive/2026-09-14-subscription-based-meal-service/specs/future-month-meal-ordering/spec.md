## REMOVED Requirements

### Requirement: Customer can create a meal order for a selected meal month

**Reason:** Customers no longer pick `year`/`month` to start a closed package. Service is an open-ended subscription.
**Migration:** Clients call subscribe with `plan_public_id`. Rolling slot generation covers current and next month. Legacy create MUST reject with subscribe-required.

### Requirement: Selected meal month must be within the allowed window

**Reason:** There is no customer-selected meal month window for purchase.
**Migration:** Horizon and unpublished-month behavior live in `subscription-delivery-continuity`.

### Requirement: Month lock and wallet minimum apply to the selected meal month

**Reason:** Month lock and order-create wallet gate are removed from purchase.
**Migration:** One active subscription exclusivity plus `subscription-wallet-eligibility` on subscribe.
