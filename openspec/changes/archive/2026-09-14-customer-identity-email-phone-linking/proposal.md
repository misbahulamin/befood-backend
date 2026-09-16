## Why

Production customers can register with email (and a referral code), then later enter a phone number and be treated as a brand-new user. Identity is split across `User.email` and `CustomerProfile.phone`, and anonymous phone OTP create-or-login only looks up by phone—so a null-phone email account never matches. That creates duplicate `User`/`CustomerProfile`/`ReferralProfile` risk, a second referral prompt, and split subscriptions/wallets on a live system.

## What Changes

- Establish a **single customer identity rule**: email **or** phone that already belongs to a customer MUST resolve to the same `User` + `CustomerProfile`; never create a second customer for a known identifier.
- Harden **phone OTP** so authenticated bind updates the existing profile, and anonymous verify only creates when the phone is truly unknown—never silently invents a parallel identity for an already-signed-in email customer.
- Clarify and document the **correct post-email phone path**: after email (or social) login with `phone_verification_required`, clients MUST use authenticated bind OTP—not anonymous phone register—so phone attaches to the same account.
- Enforce **referral once per customer**: referral input and `attribute_on_signup` apply only on true first customer creation; existing customers (login, OTP, bind, second identifier) MUST never get a referral UI path that can create attribution again.
- Add/strengthen **pre-flight identity signals** for clients (`email-check`, phone availability / existence) so mobile can skip referral and choose login vs register vs bind without guessing.
- Add **production-safe duplicate detection** (report/ops tooling only): no automatic account merge, no customer ID rewrites, no referral/wallet/subscription history mutation.
- Update backend + frontend docs and tests for the identity + referral contract. Mobile UX changes are specified as a client contract (this repo documents; app implements).

## Capabilities

### New Capabilities

- `customer-identity-linking`: Rules for resolving email and phone to one customer, when to create vs login vs bind, and live-data safety (no automatic merges).
- `referral-once-per-customer`: Referral code accepted only for brand-new customers; existing accounts and second-identifier flows must reject/ignore re-attribution.
- `auth-identity-client-contract`: Mobile/web contract for existence checks, when to show referral UI, and which phone OTP endpoints to call after email/social login.

### Modified Capabilities

<!-- No matching capability yet under openspec/specs/ for multi-provider auth or referral-program (those live under prior change folders). New capabilities above capture the requirement deltas. -->

## Impact

- **Backend apps:** `user_management` (models already split email/phone; services: `phone_otp`, `phone_availability`, `customer_factory`, `pending_registration`, OAuth wrappers, email-check), `referrals` (attribution/eligibility call sites).
- **APIs:** phone OTP send/verify, phone bind send/verify, phone check-availability, email-check, registration finalize, Google/Facebook login—additive response/docs preferred; avoid breaking auth envelopes.
- **Clients:** Mobile registration/login screens (referral section visibility, bind vs anonymous phone). Web docs updated for parity where relevant.
- **Data:** Live customers, wallets, subscriptions, referrals—detect-only tooling for duplicates; **no** destructive merge migration in this change.
- **Related prior work:** builds on `multi-provider-authentication`, `unified-customer-auth-flow`, `registration-verify-before-create`, and `referral-affiliate-commission-system` (immutable one-referrer already partially enforced).
