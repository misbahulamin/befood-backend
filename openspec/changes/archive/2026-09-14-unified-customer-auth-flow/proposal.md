## Why

Multi-provider customer auth (email, phone OTP, Google, Facebook) already exists and must stay production-safe. Clients still lack a unified registration/login UX contract: there is no explicit `phone_verification_required` signal, no email-first lookup step, and no post-email-verify phone gate—so frontend cannot reliably drive the product’s mandatory phone collection without guessing from soft onboarding hints.

## What Changes

- **Analyze-and-reuse first:** Treat `multi-provider-authentication` as the foundation. Do **not** re-implement Google/Facebook verify, phone OTP create-or-login, SocialIdentity linking, AuthSession, deferred email registration, or token migration.
- Add additive **`phone_verification_required`** boolean to the unified auth success envelope (and `/me` where clients need the same signal).
- Define clear semantics:
  - Social **new** user without verified phone → `true` (token still issued; FE runs phone OTP).
  - Social / email **existing** without verified phone → `true`, login not blocked.
  - Phone OTP success → `false`.
  - Verified phone present → `false`.
- Add **email-first check** endpoint so clients can branch: existing verified email → password login; new/pending → registration/pending path—without inventing a parallel register stack.
- After **email verification succeeds**, if the new customer has no verified phone, response must indicate phone verification is required (additive fields; preserve existing success message contract).
- Align onboarding helpers so “phone complete” considers **`is_phone_verified`**, not merely phone presence (additive behavior clarification).
- Extend tests/docs only for the new contract; **no BREAKING** removal of endpoints, fields, AuthSession keys, or legacy Token fallback.
- Do **not** invalidate existing sessions/tokens or force-logout existing users.

## Capabilities

### New Capabilities

- `email-first-auth-check`: Email-only lookup that tells the client whether to show password login vs start deferred registration (pending-aware), without creating users or leaking unnecessary account details beyond the agreed branch status.
- `phone-verification-gate`: Shared `phone_verification_required` semantics across Google, Facebook, email login, email-verify completion, phone OTP, and authenticated profile/`me` reads—prompting FE OTP without hard-blocking legacy authenticated API access.

### Modified Capabilities

<!-- No matching capability yet in openspec/specs/ for multi-provider customer auth (delta lives only under the prior change folder). New capabilities above cover the requirement deltas. -->

## Impact

- **Apps:** `user_management` services (`auth_session`, `auth_service`, email verify finalize path, OAuth login wrappers, `profile_onboarding`), API serializers/views/urls, OpenAPI, tests, `docs/backend` + `docs/frontend`.
- **Preserved:** Existing email register/login/verify, phone OTP send/verify, Google/Facebook OAuth, SocialIdentity linking priority, AuthSession + legacy Token auth, admin/deliveryman auth, additive migration `0020_*` data.
- **Clients:** Can implement one unified auth UI: method pick → email-check / social / phone → optional phone OTP when `phone_verification_required` is true.
- **Risk control:** Additive response fields and optional new route only; no token revoke, no schema removals, no hard API lockout for users missing phone.
