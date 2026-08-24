## 1. Data model & migration

- [x] 1.1 Make `CustomerProfile.phone` nullable (`null=True`, `blank=True`) while keeping `unique=True` and max_length=10
- [x] 1.2 Make `CustomerProfile.occupation` nullable/blank while keeping existing `Occupation` choices
- [x] 1.3 Make `CustomerProfile.is_bachelor` nullable (`null=True`) so unset is distinct from `False`
- [x] 1.4 Generate and review a non-destructive Django migration; confirm no data backfill clears existing customer values
- [x] 1.5 Manually verify migration applies cleanly on local DB and existing customers retain phone/occupation/`is_bachelor`

## 2. Simplified customer registration

- [x] 2.1 Update `CustomerRegistrationSerializer` so only `email` and `password` are required
- [x] 2.2 Keep legacy fields (`first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`) optional with existing validators when provided
- [x] 2.3 Ensure privileged/unknown registration fields cannot set `is_email_verified`, roles, or `is_active`
- [x] 2.4 Update `register_customer` to create `User`/`CustomerProfile` with null/empty onboarding fields when omitted; persist optional legacy values when present
- [x] 2.5 Confirm registration still assigns `CUSTOMER` group, sets `is_active=False`, and calls existing `send_activation_email` unchanged
- [x] 2.6 Update OpenAPI/schema decorators for the register endpoint request body

## 3. Email verification & login semantics (reuse only)

- [x] 3.1 Smoke-check verify-email and resend-verification paths remain unchanged (token generator, 24h expiry, anti-enumeration)
- [x] 3.2 Confirm successful verification still sets `is_email_verified`, `email_verified_at`, and `User.is_active=True`
- [x] 3.3 Confirm login allows verified customers with incomplete onboarding fields and still blocks unverified customers

## 4. Progressive profile partial updates

- [x] 4.1 Extend profile PATCH serializer allow-list to include `first_name`, `last_name`, `phone`, `occupation`, `is_bachelor` (plus existing extended fields)
- [x] 4.2 Implement atomic update of `User` names + `CustomerProfile` fields with immediate DB persistence (no session pending state)
- [x] 4.3 Reuse existing phone validation/uniqueness and enum/choice validation for gender/occupation; validate `is_bachelor` as boolean when present
- [x] 4.4 Keep privileged fields read-only / non-writable (`is_email_verified`, `email_verified_at`, `profile_completed`, `profile_completion_percentage`, groups, `is_active`)
- [x] 4.5 Ensure invalid field errors return `400` without clearing unrelated stored profile data
- [x] 4.6 Update OpenAPI examples for incremental PATCH payloads (name-only, phone-only, demographics)

## 5. Onboarding completion status

- [x] 5.1 Add derived onboarding helper/service (`missing_fields`, `completed`, optional percentage) over `first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`, `gender`
- [x] 5.2 Expose `onboarding_completion` on `GET /user_management/me/` without colliding with extended `profile_completed` / `profile_completion_percentage`
- [x] 5.3 Include the same onboarding metadata on customer profile GET/PATCH responses
- [x] 5.4 Do not add redundant DB boolean columns solely for onboarding completion

## 6. Non-customer isolation & admin safety

- [x] 6.1 Verify deliveryman registration/login behavior is unchanged
- [x] 6.2 Verify admin login and admin customer directory read paths tolerate null phone/occupation/`is_bachelor`
- [x] 6.3 Confirm profile PATCH remains restricted to authenticated customers with their own `customer_profile`

## 7. Tests

- [x] 7.1 Registration with only email+password succeeds and creates inactive user/profile
- [x] 7.2 Existing email verification still activates account
- [x] 7.3 Verified customer with incomplete profile can login; unverified cannot
- [x] 7.4 Independent PATCH updates for name, phone, gender, occupation, `is_bachelor`
- [x] 7.5 Invalid values rejected; privileged mass-assignment blocked; cross-customer update denied
- [x] 7.6 Legacy customers retain existing data; `missing_fields` / `completed` correct for partial and full onboarding
- [x] 7.7 Optional legacy registration fields still accepted when valid
- [x] 7.8 Multiple customers without phone do not violate unique constraint
- [x] 7.9 Non-customer auth tests still pass

## 8. Documentation & rollout notes

- [x] 8.1 Update `docs/customer-auth-api.md` for simplified register + compatibility window
- [x] 8.2 Update `docs/customer-profile-api.md` for progressive PATCH fields and onboarding completion payload
- [x] 8.3 Add/update `user_management/docs/frontend/` progressive onboarding contract (snake_case examples, missing_fields usage)
- [x] 8.4 Document account-registration-complete vs onboarding-profile-complete vs extended profile complete
- [x] 8.5 Note client migration: stop requiring profile fields at signup; use `/me` + PATCH after login
