## ADDED Requirements

### Requirement: Order create revalidates delivery coordinates
When a customer creates a meal package order (checkout), the system MUST resolve the delivery destination coordinates that will be used for scheduled deliveries and MUST re-run service-area verification against **active** hubs using those latitude/longitude values. The system MUST reject the order when coordinates are missing/invalid or when no active hub covers the location. The system MUST ignore any client-supplied “already verified” or `service_available` flag.

#### Scenario: Serviceable coordinates allow create path to continue
- **WHEN** a verified customer creates an order whose resolved delivery place lies inside an active hub radius and other existing eligibility rules pass
- **THEN** the service-area gate does not reject the order for coverage reasons

#### Scenario: Out-of-coverage coordinates reject order
- **WHEN** a verified customer creates an order whose resolved delivery latitude/longitude fall outside every active hub radius
- **THEN** the system rejects the create with a clear service-area error code/message and does not create the order

#### Scenario: Missing coordinates reject order
- **WHEN** a verified customer creates an order but the resolved delivery destination has no usable latitude/longitude
- **THEN** the system rejects the create with a delivery-location-required (or equivalent) error and does not create the order

### Requirement: Stale home verification cannot bypass checkout
Even if the customer previously received `service_available=true` on the Home check API, checkout MUST perform a fresh server-side coverage evaluation with current active hubs and current delivery coordinates.

#### Scenario: Hub deactivated after home check
- **WHEN** a customer was serviceable under hub A, admin deactivates hub A (and no other hub covers the point), then the customer submits checkout with the same coordinates
- **THEN** the order create is rejected as non-serviceable

#### Scenario: Customer changes delivery place before checkout
- **WHEN** a customer’s Home check used serviceable coordinates but checkout resolves a different delivery place outside all active hubs
- **THEN** the order create is rejected as non-serviceable
