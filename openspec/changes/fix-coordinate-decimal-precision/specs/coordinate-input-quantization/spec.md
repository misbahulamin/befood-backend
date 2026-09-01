## ADDED Requirements

### Requirement: Inbound coordinates are quantized to stored precision
The system SHALL accept client-supplied latitude and longitude values that contain more fractional digits than the stored `decimal_places=6` precision by quantizing to six decimal places before digit-count validation. Valid WGS84 ranges MUST still be enforced after quantization. The system MUST NOT return the “no more than 9 digits in total” error solely because a GPS float had excess precision.

#### Scenario: High-precision GPS latitude on delivery place create
- **WHEN** an authenticated customer creates a delivery place with latitude `31.915129999999998` and a valid longitude within range, plus required address fields
- **THEN** the system responds `201` and stores latitude quantized to six decimal places

#### Scenario: High-precision coordinates on location refresh
- **WHEN** a customer PATCHes location-preference refresh with high-precision GPS floats
- **THEN** the system responds `200` and updates detected coordinates without digit-count validation failure
