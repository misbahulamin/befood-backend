## ADDED Requirements

### Requirement: Active subscription generates delivery slots without email

When a customer successfully activates a subscription, the system MUST call delivery ensure logic that creates `OrderDelivery` rows for dates in the rolling horizon that have a published monthly menu for the subscribed meal package. Slot creation MUST NOT depend on `User.email` or `is_email_verified`. Preconditions for generation are: ACTIVE subscription and published menu coverage for the target year/month (plus existing meal-off/cutoff and address snapshot rules).

#### Scenario: Phone-only subscribe with published menu creates slots

- **WHEN** a phone-only identity-verified customer subscribes to a package whose current or next month menu is published
- **THEN** the system creates one or more `OrderDelivery` rows for the subscription within the ensure horizon

#### Scenario: Active subscription with unpublished menu creates zero slots

- **WHEN** a customer (phone-only or email) has an ACTIVE subscription but no published menu for the meal in the ensure horizon months
- **THEN** the system leaves the subscription ACTIVE and creates no delivery rows for unpublished months

#### Scenario: Email added later does not duplicate slots

- **WHEN** a phone-only subscriber already has delivery slots and later adds or verifies an email
- **THEN** re-running ensure MUST NOT create duplicate `(service_date, meal_period)` rows for that subscription

### Requirement: Ensure entry points include phone-only subscribers

All ensure entry points (subscribe create, current subscription retrieve, package views that ensure, cron ensure-all, and menu publish ensure) MUST process ACTIVE subscriptions regardless of email presence. Ensure-all MUST iterate ACTIVE subscriptions without filtering on `is_email_verified`.

#### Scenario: Cron ensure-all includes phone-only active subscriptions

- **WHEN** ensure-all runs and a phone-only customer has an ACTIVE subscription with published menu months
- **THEN** that subscription is included and missing slots in range are created idempotently
