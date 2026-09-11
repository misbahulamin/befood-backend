# Mobile — customer identity & referral checklist

Use with `multi-provider-auth-integration.md`. Backend is authoritative.

## Golden rules

1. **Email OR phone** on the same `CustomerProfile` = one customer.
2. Show **referral input only** when pre-check says `referral_input_allowed: true`.
3. After email/social login with `phone_verification_required: true`, use **bind OTP** — never anonymous `/phone/otp/verify/`.
4. Never show referral again on phone bind / existing login.

## Pre-check → UI

| Step | API | Referral UI |
|------|-----|-------------|
| Email entry | `POST /customer/email-check/` | Only if `referral_input_allowed` (status `available`) |
| Phone entry | `POST /phone/check-availability/` `context=login` | Only if `referral_input_allowed` (`phone_exists=false`) |
| Bind phone | `context=bind` or bind endpoints | **Never** |

## Ordered flows

### A. New email + referral → then phone

1. `email-check` → `available` → show referral once → `register` → verify email
2. Keep session / login → if `phone_verification_required` → `phone/otp/bind/send` + `bind/verify`
3. Do **not** open anonymous phone registration or referral again

### B. New phone + referral

1. `phone/check-availability` `context=login` → `phone_exists=false` → show referral
2. `phone/otp/send` + `phone/otp/verify` (anonymous) with `referral_code` + `X-Client-Type: mobile`
3. Later email: `POST /customer/profile/email/` (authenticated) — same account, no second referral

### C. Existing email

1. `email-check` → `exists` → password/login — **no referral**

### D. Existing phone

1. check-availability → `phone_exists=true` → OTP login — **no referral**

### E. Social → phone

1. Google/Facebook success → if `phone_verification_required` → **bind** only — **no referral** on phone step

## Screens to update

| Screen | Change |
|--------|--------|
| Registration (email) | Referral section only when `referral_input_allowed` |
| Registration / login (phone) | Same; hide referral when phone exists |
| Post-email / post-social phone OTP | Switch to **bind** endpoints; remove referral block |
| Login chooser (email vs phone) | Existence checks first; never treat second identifier as new signup when session exists |

## Headers

- Mobile referral attribution requires `X-Client-Type: mobile` (or `referral_client_type: mobile` where the API accepts it).
- Web must not expect referral attribution on signup.

## Warning

Calling anonymous `POST /phone/otp/verify/` while the user is already logged in with email used to risk a **second account**. Backend now binds instead; still call bind endpoints explicitly for clarity.
