## MODIFIED Requirements

### Requirement: Customer can manage a labeled delivery place book
The system SHALL allow an authenticated customer to create, list, retrieve, update, and delete (or deactivate) their own delivery places. Each place MUST expose opaque `public_id` (UUID) as the client identity. Each place MUST include a human `label` and address fields sufficient for delivery. When latitude/longitude are supplied from GPS or map sources with excess fractional precision, the system MUST quantize them to the stored coordinate precision and MUST NOT reject solely for total digit count exceeding the DecimalField digit limit prior to quantization. Delivery places MUST be independent of `present` / `permanent` identity addresses. The system MUST NOT allow a customer to access or mutate another customer’s places.

#### Scenario: Create delivery place
- **WHEN** an authenticated customer creates a delivery place with a label and full address
- **THEN** the system responds `201` with the place including `public_id`, `label`, and address fields owned by that customer

#### Scenario: Create with high-precision GPS coordinates
- **WHEN** an authenticated customer creates a delivery place including GPS latitude/longitude with more than six decimal places
- **THEN** the system accepts the request and stores quantized coordinates

#### Scenario: List own delivery places
- **WHEN** an authenticated customer requests their delivery places
- **THEN** the system responds `200` with only that customer’s places

#### Scenario: Foreign place is not found
- **WHEN** an authenticated customer requests or mutates a delivery place `public_id` belonging to another customer
- **THEN** the system responds `404 Not Found`

#### Scenario: Unauthenticated access rejected
- **WHEN** an unauthenticated client calls delivery place endpoints
- **THEN** the system responds `401 Unauthorized`
