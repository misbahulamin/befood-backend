## ADDED Requirements

### Requirement: Admin funnel distinguishes validate attempts from attributed registrations
The admin referral analytics API SHALL continue to expose attempt-based validation counters and relationship-based registration counters, and MUST document that `total_successful_validations` counts validate API successes (not unique users and not attributed signups). `total_successful_registrations` MUST equal the count of `ReferralRelationship` rows in the selected date range. `total_paid_subscribers_from_referral` MUST count distinct referred customers who have an ACTIVE meal subscription and MUST NOT require commission success.

#### Scenario: Validate without signup inflates Valid OK only
- **WHEN** clients call validate successfully many times for usable codes and no `ReferralRelationship` is created
- **THEN** `total_successful_validations` increases and `total_successful_registrations` does not

#### Scenario: Attributed signup increments registrations
- **WHEN** a brand-new mobile customer is attributed via `attribute_on_signup`
- **THEN** `total_successful_registrations` increases by one for the attribution timestamp range

### Requirement: Admin analytics expose unique successful validation codes
The admin referral analytics response SHALL include an additive field `unique_successful_validation_codes` equal to the count of distinct referral codes among `ReferralValidationEvent` rows with `is_valid=True` in the selected date range. Existing fields MUST remain for backward compatibility.

#### Scenario: Repeated validates of one code
- **WHEN** the same usable code is validated successfully ten times in range and no other codes are validated
- **THEN** `total_successful_validations` is 10 and `unique_successful_validation_codes` is 1

### Requirement: Conversion metrics remain attempt-based and labeled
The existing `conversion_rate` field SHALL remain `total_successful_registrations / total_successful_validations` (zero when denominator is zero) for backward compatibility. Documentation and admin client docs MUST state that this rate is attempt-based and MUST NOT be presented as unique-user conversion without the unique-code metric.

#### Scenario: Zero successful validations
- **WHEN** there are zero successful validations in range
- **THEN** `conversion_rate` is `0.00` (or equivalent quantized zero) and the API still returns successfully
