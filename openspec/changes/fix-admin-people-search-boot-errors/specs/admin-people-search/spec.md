## ADDED Requirements

### Requirement: Shared admin people-search Q builder

The system SHALL provide a shared service module that builds Django `Q` objects for verified-admin free-text people search. The module MUST expose `build_customer_people_q(q, *, customer_prefix='')` and `build_subscription_people_q(q)`. Matching MUST cover user email, first name, last name, username (case-insensitive contains), optional multi-word first+last pairing, phone with the same normalization used by the customer directory (optional `+880` / `880` stripping), and exact customer `public_id` when `q` is a canonical 36-character UUID. Short hex or phone-like strings MUST NOT be treated as UUID lookups.

#### Scenario: Empty query yields empty Q

- **WHEN** `build_customer_people_q` is called with blank or whitespace-only `q`
- **THEN** the returned `Q` matches all rows (no additional restriction)

#### Scenario: Email and name fragments match

- **WHEN** `q` is a fragment of a customer email or name/username
- **THEN** the built `Q` matches that customer via the corresponding identity fields under the given `customer_prefix`

#### Scenario: Phone normalization matches stored phone

- **WHEN** `q` is a BD phone variant that normalizes to digits present on the customer phone
- **THEN** the built `Q` includes a phone `icontains` condition using the normalized term

#### Scenario: Canonical UUID matches public_id only

- **WHEN** `q` is a canonical UUID matching a customer `public_id`
- **THEN** the built `Q` includes an exact `public_id` equality condition

#### Scenario: Non-canonical UUID-like term is not a public_id lookup

- **WHEN** `q` is a short hex or numeric string that is not a 36-character UUID
- **THEN** the built `Q` MUST NOT add a `public_id` equality condition for that term

### Requirement: Subscription people-search includes subscription public_id

`build_subscription_people_q` MUST compose customer people-search with `customer_prefix='customer__'` and, when `q` is a canonical UUID, MUST also match the subscription row's own `public_id`.

#### Scenario: Search by subscription public_id

- **WHEN** a verified admin filters subscriptions with `q` equal to a subscription `public_id`
- **THEN** that subscription is included in the filtered queryset

### Requirement: Admin surfaces reuse the shared builder

Verified-admin list search for customers, support conversations (customer side of `q`), admin subscriptions, and admin wallet funding requests MUST call the shared builders rather than duplicating divergent field lists. Domain-only extras (for example support `last_message` text) MAY be OR-ed at the call site after the shared people `Q`.

#### Scenario: Customer directory uses shared builder

- **WHEN** admin customer list applies `q`
- **THEN** filtering uses `build_customer_people_q` without a local duplicate name/email/phone-only `Q`

#### Scenario: Wallet funding list uses shared builder with wallet prefix

- **WHEN** admin wallet funding list applies `q`
- **THEN** filtering uses `build_customer_people_q` with `customer_prefix` rooted at the funding request's related customer

#### Scenario: Support inbox customer portion uses shared builder

- **WHEN** admin support conversation list applies `q`
- **THEN** customer identity matching uses `build_customer_people_q` with `customer_prefix='customer__'`

### Requirement: Django application imports remain boot-safe

The shared module's exported names and all import sites MUST stay consistent so URL configuration imports succeed. A rename of a public helper MUST update every caller in the same change. Syntax in modules imported by `core.urls` MUST be valid Python.

#### Scenario: System check succeeds after fix

- **WHEN** an operator runs `python manage.py check` on the fixed branch
- **THEN** the command completes without `ImportError` or `SyntaxError` from people-search or wallet funding OpenAPI modules

#### Scenario: Stale helper name is not imported

- **WHEN** the codebase is searched for `build_subscription_search_q`
- **THEN** no production import of that name remains
