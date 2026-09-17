## MODIFIED Requirements

### Requirement: Admin approve response reports meal service restore outcome

On a successful admin funding approve response for a recharge, the system SHALL include a boolean field `meal_service_restored` that equals the boolean returned by `maybe_resume_after_wallet_credit` for that approval (or `false` when resume is not evaluated). The field MUST be `true` only when that approval cleared the customer’s low-balance meal-stop block, and `false` otherwise (including when the customer was not blocked, remained below threshold after credit, or the approved request is a withdraw). Existing approve success fields MUST remain available; adding `meal_service_restored` MUST NOT break clients that ignore unknown fields. Frontend clients MUST NOT compute meal-stop resume themselves. No database migration is required for this field. Admin **reject** responses for withdraw MAY return `meal_service_restored=true` when reject clears meal-stop; that reject behavior is owned by `meal-service-resume-on-withdraw-reject` and MUST NOT be inferred as always `false` solely because the HTTP action is reject.

#### Scenario: Approve response indicates meal service restored

- **WHEN** a verified admin approves a pending recharge that clears meal-stop for a previously blocked customer
- **THEN** the HTTP success response includes `meal_service_restored` set to `true`

#### Scenario: Approve response indicates meal service not restored

- **WHEN** a verified admin approves a pending recharge for a blocked customer whose post-credit balance remains below `meal_stop_threshold`
- **THEN** the HTTP success response includes `meal_service_restored` set to `false`

#### Scenario: Withdraw approve does not claim meal service restored

- **WHEN** a verified admin successfully approves a pending withdraw
- **THEN** the HTTP success response includes `meal_service_restored` set to `false` and meal-stop block fields are not cleared by withdraw approval
