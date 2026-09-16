## Why

Multi-provider authentication (email, phone OTP, Google, Facebook) is live, but customer feature gates still treat `CustomerProfile.is_email_verified` as the only trusted identity. Phone-only and social users can authenticate successfully yet are blocked from orders, subscriptions, and related actions with “Email verification is required…”. Identity trust must follow the provider that actually verified the customer.

## What Changes

- Introduce a single customer identity-verification helper (`is_customer_identity_verified`) used by all customer feature gates (extensible for future providers such as Apple / WhatsApp).
- Treat a customer as identity-verified when **any** of: email verified, phone verified, Google social identity linked, Facebook social identity linked.
- Derive Google/Facebook trust from `SocialIdentity` (no denormalized `is_google_verified` / `is_facebook_verified` columns).
- Replace email-only checks in order placement, subscription, `IsVerifiedCustomer`, and any other customer business gates that currently require `is_email_verified` (search must cover field names **and** message strings).
- Apply identity gates only to authenticated customers; do not alter guest/anonymous checkout or location flows.
- Keep email verification for email ownership, recovery, and messaging; do **not** treat Google/Facebook login alone as automatic `is_email_verified=True` unless policy explicitly trusts a provider-asserted verified email.
- Harden auth/response builders for phone-only users where `user.email` may be null/empty (no unsafe `.lower()` on null email).
- Add unified `verification_status` (including `identity_verified`) on customer auth success responses.
- Change gate error copy to identity-oriented English API text; document Bangla UI copy for clients.
- **Non-breaking** for existing email-verified customers: `is_email_verified=True` continues to satisfy the new rule (no migration).

## Capabilities

### New Capabilities

- `customer-identity-verification`: Unified customer identity trust rule, helper API, auth `verification_status` contract, authenticated-only feature gates, null-safe phone-user handling, provider-vs-email ownership clarity, and replacement of email-only customer access gates.

### Modified Capabilities

- (none in main `openspec/specs/` — current email-only gates are implementation-level; multi-provider auth login mechanics unchanged except clarifying social→email verification policy where needed)

## Impact

- **Models / services**: `CustomerProfile` (`is_email_verified`, `is_phone_verified`), `SocialIdentity` (Google/Facebook), new `user_management.services.identity_verification`, auth session / response builders (null-safe email).
- **Gates**: `orders.api.permissions.IsVerifiedCustomer`, order/subscription serializers, other customer access checks found via broad search; **not** guest endpoints.
- **Auth responses**: email, phone, Google, Facebook success payloads via `auth_session` / auth services + `verification_status`.
- **Errors / docs**: identity-oriented English messages; frontend docs with Bangla UI example; clients stop assuming email is universal.
- **Tests**: phone/Google/Facebook users can place orders; email-verified users unchanged; email-only unverified blocked; guest flows unchanged; null-email phone users safe.
- **Out of scope**: Delivery Man email gates; admin directory email filters; implementing Apple/WhatsApp (helper must remain easy to extend).
