## REMOVED Requirements

### Requirement: One non-cancelled meal package per order month

**Reason:** Customers no longer purchase a closed monthly package. Exclusivity is one active subscription per customer, not one order per `YYYY-MM`.
**Migration:** Enforce uniqueness on `CustomerSubscription` with `status=active`. Historical non-cancelled orders remain read-only and do not start new service.

### Requirement: Month lock is enforced in the order creation service

**Reason:** `create_meal_order` is retired as the customer purchase path.
**Migration:** Put exclusivity in the subscribe service. Legacy `POST` order create MUST reject with subscribe-required rather than applying month lock.
