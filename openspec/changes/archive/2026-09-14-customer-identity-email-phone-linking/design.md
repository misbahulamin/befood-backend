## Context

BeFood customer identity is split today:

| Identifier | Storage | Uniqueness |
|---|---|---|
| Email | `User.email` | Practically unique via registration checks; not a single DB unique on profile |
| Phone | `CustomerProfile.phone` | `unique=True`, nullable |

`CustomerProfile` is `OneToOne(User)`. Referral attribution runs at customer **creation** (`attribute_on_signup` from pending finalize, phone OTP verify when `created=True`, OAuth create paths). Attribution already rejects a second relationship for the same `referred` (`REFERRAL_ALREADY_ATTRIBUTED`), but a **second CustomerProfile** for the same human bypasses that guard.

### Current flow (bug path)

```text
Email register + referral
  → PendingCustomerRegistration (stores referral_code)
  → verify → User + CustomerProfile(phone=NULL) + ReferralRelationship
  → auth token issued; phone_verification_required may be true

Later, unauthenticated phone OTP verify (018…)
  → lookup CustomerProfile.phone == 018… → miss (phone was NULL)
  → create_phone_only_customer() → NEW User + CustomerProfile + ReferralProfile
  → created=True → referral_code accepted again on a NEW referred customer
```

Authenticated bind already exists and is the correct technical path:

```text
POST /phone/otp/bind/send/ + /phone/otp/bind/verify/
  → updates same CustomerProfile.phone; no new User; no referral
```

Root cause is therefore **backend + mobile together**: backend anonymous phone path cannot know which email account owns an unused phone; mobile appears to restart registration (referral UI) via anonymous create-or-login instead of bind after email session.

Constraints: production has customers, wallets, subscriptions, referrals, meal history. No automatic ID merge. No rewrite of referral history.

## Goals / Non-Goals

**Goals:**

- One logical customer identity: login with email **or** phone when both are on the same profile.
- After email/social account exists, verifying a phone MUST update that profile when the user is authenticated (bind).
- Referral UI and attribution only for **true new** customers; never for login, bind, or second-identifier attachment.
- Clear client contract so mobile skips referral for existing identifiers and uses bind after email/social.
- Ops-safe duplicate detection report (read-only); no silent merge.
- Tests covering email→phone same account, phone→email same account, referral once, subscription continuity.

**Non-Goals:**

- Automatic merge of already-duplicated production accounts.
- Changing customer primary keys / public IDs.
- Rewriting historical `ReferralRelationship` / commissions / wallets.
- Requiring phone on every legacy account before API access (keep soft `phone_verification_required` gate).
- Building the mobile app in this repo (document contract only).
- Unifying email onto `CustomerProfile` or phone onto `User` in this change (keep current columns; fix resolution logic).

## Decisions

### 1. Identity resolution rule (create vs reuse)

**Decision:** Before creating any new `User`/`CustomerProfile`, resolve:

1. If phone matches an existing `CustomerProfile.phone` → that customer (login / verify flags).
2. If email matches an existing customer `User.email` → that customer (email paths).
3. Else → new customer (only place referral may apply).

**Anonymous phone OTP cannot attach to an email-only account** solely because “same human”—there is no stored link yet. Linking requires either:

- Authenticated **bind** (preferred after email/social login), or
- A future explicit verified link flow (out of scope unless product demands cold linking).

**Alternatives considered:** Auto-merge on phone verify by fuzzy match (name) → rejected (unsafe). Prompt anonymous phone user for email+password to link → deferred (extra UX; can be phase 2).

### 2. Fix the production bug primarily via bind + client contract + backend guards

**Decision:**

1. Treat authenticated bind as the canonical “add phone to email account” path (already implemented; harden + document).
2. When `verify_phone_otp` is called with an authenticated customer session (if clients mistakenly hit anonymous verify while logged in), prefer bind semantics or reject create—do not create a second profile.
3. Mobile MUST: after email/social success with `phone_verification_required=true`, call bind OTP endpoints with the session token; MUST NOT open new-registration referral UI.
4. `phone_exists` / email-check drive referral visibility: show referral only when identifier is new.

**Alternatives considered:** Remove anonymous phone account creation entirely → too breaking for phone-first users. Always require email before phone → product regression.

### 3. Referral once-per-customer (immutable + no second creation)

**Decision:**

- Keep `ReferralRelationship.referred` unique / `attribute_on_signup` immutability.
- Ensure every create path that accepts `referral_code` only runs when `created=True` for a brand-new profile.
- Bind, login, OAuth existing-user, email login: ignore or reject referral_code with a stable error; never create attribution.
- If a customer already exists (any login method), clients MUST hide referral input (documented). Backend remains source of truth.

**Alternatives considered:** Allow changing referrer → rejected by product (“once registered / once used, never again”).

### 4. Phone→email later (symmetric case)

**Decision:** Phone-first customer later adds email via authenticated profile / set-email+verify flows (existing or small additive), updating the same `User.email` when free. Do not create a second user. Email register against a phone that already exists as pending conflict stays as today (validation errors).

### 5. Live duplicate handling

**Decision:** Ship a read-only management command / report that lists suspected duplicate pairs (e.g. same normalized phone on one profile and empty phone + later phone-only user patterns are hard; focus on exact phone uniqueness already enforced + ops notes for support merges). **Manual** support merge playbook only; no automated merge migration in this change.

### 6. Data model

**Decision:** Keep `User.email` + `CustomerProfile.phone`. Add no identity-merge table in v1. Optionally add indexes/docs only. Future “IdentityLink” table is out of scope.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Mobile still calls anonymous phone verify after email login → duplicate accounts | Document bind contract; backend guard if authenticated user hits create path; add response flag `account_created` already usable; consider rejecting create when Authorization present |
| Existing duplicates already in production | Detect-only command + support playbook; no auto-merge |
| Users expect cold phone OTP to “find” their email account | Explicit product messaging: after email signup, stay logged in and verify phone; or login with email first then bind |
| Referral fraud via intentional second account with new phone | Phone uniqueness helps; email uniqueness helps; full device fraud out of scope; referral still once per **account** |
| Breaking phone-first registration | Keep anonymous create when phone unknown |
| OAuth + referral edge cases | Only attribute when `created=True` on social factory path |

## Migration Plan

1. Deploy backend guards + docs + tests (no destructive migration).
2. Release mobile using bind after email/social + referral visibility from existence checks.
3. Run duplicate detection command in read-only mode; ops triage.
4. Rollback: feature is mostly additive guards; revert commit if needed. No schema rollback required if no new migration; if a report-only migration is added, it must be reversible/no-op for data.

## Open Questions

1. Should anonymous `POST /phone/otp/verify/` with a valid `Authorization` customer token hard-fail with `USE_BIND_ENDPOINT` instead of creating? (**Recommend: yes.**)
2. Phase-2 cold link: after phone OTP for unknown phone, allow optional “already have email?” password verify to merge into existing email account—product approval needed before build.
3. Support merge tool for already-duplicated pairs—separate change after detection metrics.
