# Customer identity create-path audit

Snapshot for `customer-identity-email-phone-linking` (live-safe; no auto-merge).

## Create paths that mint `User` + `CustomerProfile`

| Path | Service | Accepts `referral_code`? | Notes |
|------|---------|--------------------------|-------|
| Email pending finalize | `pending_registration.finalize_pending_registration` | Yes (from pending row; mobile-only attribution) | Creates after email OTP/link verify |
| Anonymous phone OTP | `phone_otp.verify_phone_otp` → `create_phone_only_customer` | Yes only when `created=True` | Lookup by `CustomerProfile.phone` only |
| Social Google/Facebook | `social_linking.resolve_or_create_social_user` → `create_social_customer` | Yes only when `created=True` in OAuth wrappers | Links by SocialIdentity / verified email / verified phone first |
| Direct factory | `customer_factory.create_phone_only_customer` / `create_social_customer` | No (caller applies referral) | Internal helpers |

## Authenticated phone bind (no new User)

| Path | Service | Referral? |
|------|---------|-----------|
| `POST /phone/otp/bind/send/` + `/bind/verify/` | `bind_phone_otp_to_user` | Never — updates same `CustomerProfile` |

Confirmed: bind sets `phone` + verification flags on the authenticated profile; does not call `attribute_on_signup` or `create_*_customer`.

## Production bug (pre-fix)

1. Email register + referral → `CustomerProfile.phone = NULL`
2. Client calls **anonymous** `POST /phone/otp/verify/` instead of bind
3. Phone lookup misses → new phone-only customer + optional second referral

## Post-fix contract

- After email/social with `phone_verification_required=true` → **bind** endpoints only
- Authenticated call to anonymous verify → bind semantics (never create)
- Anonymous verify: phone hit → login; miss → create once + referral only then
- Referral UI only when identifier is new (`referral_input_allowed`)

## Regression scenario (tests)

Email account (phone null) + authenticated session hitting anonymous phone verify must **not** create a second `User`.
