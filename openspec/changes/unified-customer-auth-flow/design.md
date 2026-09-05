## Context

Production customer auth already ships multi-provider support from `multi-provider-authentication`:

- Deferred email registration (`PendingCustomerRegistration`) → verify → User + `CustomerProfile`
- Email/password login with unified AuthSession envelope
- Phone OTP send/verify create-or-login (`is_phone_verified=True`)
- Google / Facebook OAuth via `resolve_or_create_social_user` (identity → verified email → verified phone → create)
- Unified builder: `build_customer_auth_response()` in `auth_session.py`
- Additive models: `SocialIdentity`, `PhoneAuthOTP`, `AuthSession`, `is_phone_verified`

**Gaps vs product UX:**

| Need | Current |
|------|---------|
| `phone_verification_required` on auth success | Missing |
| Email-first “exists vs new” check | Separate register vs login only |
| Post-email-verify phone mandatory signal | Verify returns message only |
| Onboarding phone = verified | Onboarding checks phone presence only |

Constraints: additive only; do not invalidate tokens; do not block existing users from login; reuse existing phone OTP endpoints for the FE prompt flow.

## Goals / Non-Goals

**Goals:**

- One shared helper for `phone_verification_required` based on `CustomerProfile.is_phone_verified`.
- Include that boolean on every customer auth success envelope and on `/me` (and profile reads if already exposing onboarding).
- Email-first check API for client branching without creating users.
- After email verification creates/activates the customer, indicate phone verification is required when phone is not verified.
- Keep social/email login issuing tokens even when phone is missing (FE-driven gate, not server hard lockout).
- Align onboarding `phone` missing-field logic with verification state.
- Tests + docs for the new contract only.

**Non-Goals:**

- Rebuilding Google/Facebook/phone OTP/email deferred registration.
- Hard-blocking authenticated APIs until phone is verified (would break existing sessions and partial profiles).
- Changing AuthSession key format or removing legacy Token fallback.
- Admin / deliveryman auth changes.
- Interactive account-merge UI.
- Apple Sign-In.

## Decisions

### 1. Soft gate via response flag (not hard API lockout)

**Decision:** `phone_verification_required = not profile.is_phone_verified`. Auth endpoints still return `200` + `token` when credentials are valid. Frontend MUST run phone OTP when the flag is true for registration completion UX; backend does not revoke access for legacy users.

**Why:** Product requires phone collection for new social/email registration completeness, but also requires existing users without phone to keep logging in. Hard middleware would break production sessions.

**Alternatives considered:** Deny token until phone verified — rejected (breaks existing users / social returning users). Separate “limited token” — rejected (extra auth complexity, not requested).

### 2. Single helper on unified envelope

**Decision:** Add `phone_verification_required` inside `build_customer_auth_response()`. Derive via small helper (e.g. `is_phone_verification_required(profile)`). Mirror the same field on `CurrentUserSerializer` / `me` for post-login prompts.

**Why:** All providers already go through the builder; one place avoids drift.

### 3. Email-first check is additive lookup only

**Decision:** New endpoint, e.g. `POST /user_management/customer/email-check/` with `{ "email": "..." }`.

Normalized email outcomes:

| Status | Meaning | Client next step |
|--------|---------|------------------|
| `exists` | Production customer with verified email | Password login |
| `pending` | `PendingCustomerRegistration` for email | Resume verify / register UX |
| `available` | Neither | Collect password → deferred register |

Do **not** return password hashes, tokens, or full profile. Apply same throttling pattern as register/login where practical. Use `normalize_email()`.

**Why:** Matches email-first UX without merging login+register into one mutating endpoint.

**Anti-enumeration:** Returning `exists` vs `available` is intentional for this product UX (same as many consumer apps). Document the trade-off; keep responses minimal.

### 4. Post-email-verify phone signal

**Decision:** Keep existing verify success message and status. Add additive fields, e.g.:

```json
{
  "message": "Email verified successfully. You can now login.",
  "phone_verification_required": true,
  "email_verified": true
}
```

Do **not** auto-issue auth token on verify in this change (would alter FE “verify → login” flows). After login, envelope also carries `phone_verification_required`.

**Why:** Additive and backward compatible; FE can optionally jump to phone OTP after verify or after first login.

### 5. Social new vs returning — same flag rule

**Decision:** No special “created_user” bit required for the boolean: any auth success without `is_phone_verified` sets `phone_verification_required: true`. New Google/Facebook users without phone therefore get `true`; returning users with verified phone get `false`.

**Why:** Simpler, matches “if verified phone already → direct login (no prompt)” and “if not → indicate required.”

### 6. Phone OTP remains the completion path

**Decision:** Reuse `POST .../phone/otp/send/` and `.../verify/`. Authenticated phone-link for logged-in users without phone MUST work via existing or minimally extended OTP verify that sets `is_phone_verified` on the current profile when binding a new phone (if current verify only create-or-login by phone, document FE flow: verify OTP with that phone → same account via linking / authenticated bind). Prefer extending verify/send to support authenticated “bind phone to current user” if create-or-login would create a duplicate—only if analysis shows a gap; otherwise document the safe path.

**Implementation note (apply phase):** Before coding, confirm whether logged-in email/social users can attach a phone through current OTP verify without creating a second User. If not, add an additive authenticated bind path in the same change’s tasks.

### 7. Onboarding alignment

**Decision:** Treat onboarding field `phone` as present only when `profile.is_phone_verified` is true (or when phone is set **and** verified—prefer verified). Unverified phone remains in `missing_fields` as `phone` for FE consistency with the gate flag.

**Why:** Prevents “phone filled but unverified” from looking complete.

### 8. No new migrations unless bind path needs it

**Decision:** Prefer zero schema change. Existing `is_phone_verified` / `phone_verified_at` are enough. New migration only if an additive model field is proven necessary (unlikely).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Hard lockout accidentally shipped | Spec/tests assert login 200 + token when phone missing; no auth middleware gate |
| Email-check enumeration | Minimal status payload; rate limit; document intentional UX |
| Duplicate User if OTP verify creates new account for logged-in social user | Apply-phase gap check; add authenticated phone-bind if needed |
| FE ignores flag | Docs + frontend integration notes with clear flow diagrams |
| Onboarding % drop for users with unverified phone | Document as intentional additive behavior; flag is source of truth for auth UX |
| Drift if some auth path bypasses builder | Grep/tests assert `phone_verification_required` on email/phone/google/facebook |

## Migration Plan

1. Deploy code-only (or with optional authenticated phone-bind) — no token invalidation.
2. Clients ignore unknown fields until they adopt `phone_verification_required` and email-check.
3. Rollout FE unified flow behind feature flag if desired.
4. Rollback = revert deploy; no DB rollback required if no migration.

## Open Questions

- Exact status enum names for email-check (`exists` / `pending` / `available` vs alternatives) — default as above unless product prefers different labels.
- Whether email-verify should optionally auto-login later — out of scope unless product insists; current decision is no auto-login.
