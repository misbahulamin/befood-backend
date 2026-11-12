## ADDED Requirements

### Requirement: Pending email registration preserves referral intent when code omitted
For deferred email customer registration, when an active pending row already stores a non-empty `referral_code` and a later register submit for the same email omits `referral_code` (empty or absent after normalization), the system MUST retain the previously stored `referral_code`, `referrer_snapshot_id`, `referral_client_type`, and `referral_intent_created_at`. A later submit that includes a different non-empty `referral_code` MUST replace the stored intent with the new code and refresh snapshot/client/intent timestamp according to existing pending rules. Attribution MUST still occur only at finalize for brand-new customers under mobile-only rules.

#### Scenario: Second register without code keeps prior intent
- **WHEN** a mobile client creates pending registration with a usable `referral_code` and later re-submits register for the same email without `referral_code`
- **THEN** the pending row still contains the original referral code and client type for finalize

#### Scenario: Second register with new code replaces intent
- **WHEN** a pending registration already has code A and a later register submit includes code B
- **THEN** the pending row stores code B for finalize and no longer treats A as the intent
