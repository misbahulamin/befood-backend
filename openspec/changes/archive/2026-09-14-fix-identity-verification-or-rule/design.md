## Context

Screenshot and production reports show Confirm Recharge blocked with Bangla:

```text
আপনার অ্যাকাউন্ট যাচাই সম্পন্ন হয়নি।
দয়া করে একটি যাচাইকৃত মাধ্যম দিয়ে অ্যাকাউন্ট নিশ্চিত করুন।
```

That string is the **recommended FE identity-failure copy** from `remove-email-verification-dependency`—not an email-specific API string. So the mobile app believes identity is incomplete even when one factor succeeded.

**Backend today (OR already):**

| Layer | Behavior |
|-------|----------|
| `is_customer_identity_verified` | `email OR phone OR Google OR Facebook` |
| `IsVerifiedCustomer` / `IsVerifiedWalletCustomer` | Uses that helper |
| Auth success envelope | Includes `verification_status.identity_verified` |
| `phone_verification_required` | Soft FE flag: `not is_phone_verified` — true even when email already verified |

**Likely production bug (client + API gap):**

1. `GET /me/` (`CurrentUserSerializer`) and customer profile serializers expose `is_email_verified`, `is_phone_verified`, and `phone_verification_required`, but **omit** `verification_status` / `identity_verified`.
2. Mobile may hard-block wallet when `phone_verification_required === true`, or require `email_verified && phone_verified`, after refreshing state from `/me`.
3. Email-verified user without phone → soft flag true → false “not verified” toast (matches Case 1). Phone-only may fail if app requires email (Case 2).

Prior wallet-scoped change `phone-verified-wallet-access` clarified wallet permission messaging; this change fixes the **cross-feature OR contract and `/me` signal**.

## Goals / Non-Goals

**Goals:**

- One canonical OR rule for all customer “verified feature” access.
- `/me` and profile return `verification_status` so clients can hard-gate correctly after login.
- Soft phone prompt never confused with hard identity denial in docs or client checklists.
- Matrix tests for email-only and phone-only on wallet + at least one other gated feature (subscribe or order permission).
- Production-safe mobile handoff plan.

**Non-Goals:**

- Making phone OTP mandatory before wallet for email-verified users.
- Changing admin/deliveryman verification.
- Implementing mobile code inside this backend repo.
- Schema migrations for new verification columns.

## Decisions

### 1. Keep OR helper; do not add AND anywhere

**Choice:** Continue using `is_customer_identity_verified` as the only hard business gate. Audit and fix any residual email-only or email∧phone checks.

**Alternatives:** Separate “wallet verified” flag (drift); require phone for everyone (product rejection).

### 2. Add `verification_status` to `/me` and customer profile responses

**Choice:** Additive field on `CurrentUserSerializer` and `CustomerExtendedProfileSerializer` (same shape as auth envelope via `build_verification_status`).

**Why:** Auth login already returns it; post-login `/me` refresh must not drop the aggregate.

**Alternatives:** Top-level `identity_verified` only (less complete); force clients to OR the booleans themselves (error-prone—current failure mode).

### 3. Soft vs hard gate contract (explicit)

| Flag | Meaning | Client action |
|------|---------|---------------|
| `verification_status.identity_verified` | Hard trust | If false → show identity Bangla / block verified features |
| `phone_verification_required` | Soft onboarding | Prompt bind OTP; **do not** block wallet/subscribe if identity true |
| `is_email_verified` / `is_phone_verified` | Per-factor | Display only; never AND for access |

### 4. Mobile plan is mandatory documentation, optional if already correct

**Choice:** Document checklist in `user_management/docs/frontend/` (and cross-link wallet mobile impact). Mobile must change if it ANDs flags or hard-blocks on `phone_verification_required`.

### 5. Bangla copy usage

**Choice:** Keep the existing Bangla string **only** when `identity_verified === false`. Do not show it when email is verified and only phone bind is pending.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Mobile still ANDs after backend ships | Clear checklist + example payloads; coordinate release |
| Clients parse only auth once and never `/me` | Still add `/me` field; auth envelope already correct |
| Soft phone product later becomes hard | Separate product change; do not overload this flag |
| Overlap with `phone-verified-wallet-access` | Reuse wallet permission; focus this change on identity contract + `/me` + matrix |

## Migration Plan

1. Deploy backend: `/me`/profile `verification_status` + any gate fixes + tests.
2. Verify API: email-only and phone-only → `identity_verified: true`; email-only → `phone_verification_required: true` still.
3. Ship mobile fix if needed: hard-gate on `identity_verified` only.
4. Rollback: remove additive serializer fields (safe); no DB migration.

## Open Questions

- Confirm with one production HAR/log whether recharge fails client-side before HTTP or after backend `403` (screenshot toast matches client identity copy—likely client-side).
- Whether bind-phone UX stays mandatory in onboarding wizard while wallet remains unlocked (product: soft prompt only).
