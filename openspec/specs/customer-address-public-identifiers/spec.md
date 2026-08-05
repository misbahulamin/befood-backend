# Customer Address Public Identifiers

## Purpose
Expose customer delivery addresses through stable public UUIDs while keeping integer primary keys internal.

## Requirements

### Requirement: CustomerAddress has public UUID identity

The system SHALL store a unique `public_id` on every `CustomerAddress`. Address list/detail/update/delete APIs MUST look up and serialize by `public_id`. Customer responses MUST NOT expose integer address `id` after cutover.

#### Scenario: Address list returns public_id

- **WHEN** a customer lists delivery addresses
- **THEN** each address includes `public_id` and does not include integer `id`

#### Scenario: Address update by UUID

- **WHEN** a customer patches `/user_management/customer/addresses/<public_id>/`
- **THEN** the matching address is updated

#### Scenario: Set default uses public_id

- **WHEN** a customer sets a default delivery address
- **THEN** the request identifies the address by `public_id` (or an equivalent UUID field name documented for that action)

### Requirement: Profile nested addresses follow the same identity

If customer profile responses nest address objects, those nested objects MUST use `public_id` consistently with the address collection API.

#### Scenario: Profile nested address identity

- **WHEN** profile payload includes addresses
- **THEN** each nested address uses `public_id` rather than integer `id`
