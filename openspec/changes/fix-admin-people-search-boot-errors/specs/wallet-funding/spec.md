## ADDED Requirements

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
