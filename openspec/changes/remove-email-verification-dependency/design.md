## Context

Multi-provider authentication already creates customers via email OTP, phone OTP, Google, and Facebook. `CustomerProfile` stores `is_email_verified` / `is_phone_verified`. Social logins persist `SocialIdentity` rows (`provider` + `provider_user_id`).

Customer feature access still gates on email only:

- `orders.api.permissions.IsVerifiedCustomer` → `profile.is_email_verified`
- Order serializers → “Email verification is required before placing an order.”
- Subscription serializers → same email-only rule

Phone/social users authenticate and receive tokens, then fail those gates. Email verification itself must remain for ownership, recovery, and messaging. Phone-only accounts may have null/empty `User.email`. Guest/anonymous flows must stay independent of this identity gate.

## Goals / Non-Goals

**Goals:**

- One helper defines customer identity trust for all authenticated customer feature gates; easy to extend for future providers (Apple, WhatsApp, etc.).
- Any one verified provider identity unlocks normal customer access (orders, subscriptions, and other previously email-gated customer actions).
- Auth success responses expose per-provider flags plus aggregate `identity_verified`.
- Existing `is_email_verified=True` customers keep full access with no schema migration.
- Identity gates run only for authenticated customers; guest/anonymous behavior unchanged.
- Response builders remain null-safe for phone-only users (`email` null/empty).
- Provider identity and email ownership stay separate concepts.
- Gate API errors use identity-oriented English; docs give Bangla UI guidance for clients.

**Non-Goals:**

- Removing or weakening the email verification OTP/link system.
- Changing Delivery Man email-verification / admin-approval flows.
- Changing admin customer directory filters that intentionally surface email verification for ops.
- Requiring phone verification for email/social users (soft onboarding gate stays separate via `phone_verification_required`).
- Implementing Apple / WhatsApp login in this change.
- Changing guest checkout / guest location product rules beyond ensuring identity gates do not apply to them.

## Decisions

### 1. Central helper in `user_management.services.identity_verification`

**Choice:** Add `is_customer_identity_verified(user)` (and helpers to build `verification_status`) as the only business gate for “trusted customer identity.”

**Logic:**

```text
identity_verified =
  profile.is_email_verified
  OR profile.is_phone_verified
  OR SocialIdentity(user, google) exists
  OR SocialIdentity(user, facebook) exists
```

Future providers add another OR / lookup branch in this helper only—call sites stay unchanged.

**Why:** Prevents duplicated OR logic; matches multi-provider reality; keeps Apple/WhatsApp extension cheap.

**Alternatives considered:**

- Keep checking `is_email_verified` per module → rejected; broken for phone/social.
- Put logic only on `IsVerifiedCustomer` → rejected; serializers duplicate and drift.

### 2. Do not add denormalized `google_verified` / `facebook_verified` columns

**Choice:** Derive Google/Facebook verification from existing `SocialIdentity` rows. Keep boolean columns only for email/phone (`is_email_verified`, `is_phone_verified`).

**API mapping** (response / helper surface):

| Response field | Source |
| --- | --- |
| `email_verified` | `CustomerProfile.is_email_verified` |
| `phone_verified` | `CustomerProfile.is_phone_verified` |
| `google_verified` | `SocialIdentity` with `provider=google` for user |
| `facebook_verified` | `SocialIdentity` with `provider=facebook` for user |
| `identity_verified` | OR of the above |

**Why:** Avoid dual source of truth (`SocialIdentity` present but `is_google_verified=False`).

### 3. Authenticated-only identity gates; guest flows untouched

**Choice:** `is_customer_identity_verified` and replacements of email gates apply only after normal authentication establishes a customer user. Guest/anonymous checkout, location, or other guest-supported paths MUST keep existing behavior and MUST NOT newly require identity verification.

**Why:** Prevents accidental breakage of guest flows when rewriting permissions/serializers.

### 4. Provider identity ≠ email ownership

**Choice:** Successful Google/Facebook auth:

- MUST create/link `SocialIdentity` → `google_verified` / `facebook_verified` true → `identity_verified` true.
- MUST NOT set `is_email_verified=True` merely because a social login succeeded or because an email string is present.
- MAY set `is_email_verified=True` only when product policy explicitly trusts a **provider-asserted verified email** (e.g. Google `email_verified` claim is true). Facebook “email present” alone is insufficient.

**Why:** Email ownership and provider identity are separate; conflating them reintroduces false email trust.

**Implementation note:** Audit `google_oauth` / `facebook_oauth` / `social_linking` during apply; tighten any path that marks email verified from “email present” without a verified-email assertion.

### 5. Null-safe phone-only profile / auth builders

**Choice:** Auth and profile response builders MUST tolerate `user.email` null or empty. Never call `.lower()` / normalize on email without a null/empty guard. Phone-only users may expose `email: ""` or omit meaningfully empty email consistently with current API conventions.

**Why:** Phone OTP users often have no email; unsafe string ops crash auth success paths.

### 6. Replace customer business gates; broaden the search

**Choice:** Swap email-only access checks in:

- `IsVerifiedCustomer` (message → identity-focused English)
- Order create/validate serializers
- Subscription create serializers
- Any other **authenticated customer** access gate found by searching:

```text
is_email_verified
email_verified
Email verification is required
verified customer
```

**Keep unchanged:**

- Pending email registration finalization
- Email OTP/link verify endpoints
- Deliveryman / admin email gates
- Admin customer list email filter/display
- Guest/anonymous flows

### 7. Auth envelope: additive `verification_status`

**Choice:** Extend `build_customer_auth_response` with:

```json
"verification_status": {
  "email_verified": false,
  "phone_verified": true,
  "google_verified": false,
  "facebook_verified": false,
  "identity_verified": true
}
```

Keep existing `customer_profile.is_email_verified` / `is_phone_verified` for backward compatibility (additive, not **BREAKING**).

### 8. Error messaging (API English + FE Bangla guidance)

**Choice:**

- API / permission `message` (English): e.g. `Identity verification is required before placing an order.`
- Frontend docs recommend Bangla UI, e.g.:

```text
আপনার অ্যাকাউন্ট যাচাই সম্পন্ন হয়নি।
দয়া করে একটি যাচাইকৃত মাধ্যম দিয়ে অ্যাকাউন্ট নিশ্চিত করুন।
```

Email-specific copy remains only on email verification / resend flows.

### 9. Phone / social persistence (verify, don’t redesign)

**Choice:** Confirm:

- Phone OTP success → `is_phone_verified=True` (+ timestamp)
- Google/Facebook success → `SocialIdentity` row
- Email OTP/link → `is_email_verified=True`

Apply Decision 4 when auditing social→email flag writes.

### 10. Permission class naming

**Choice:** Keep `IsVerifiedCustomer` name; change implementation + `message` only.

## Risks / Trade-offs

- **[Risk] Missed gate still checks email only** → Mitigation: broad string search (fields + messages); regression tests for phone/Google/Facebook order/subscribe.
- **[Risk] Guest flow accidentally gated** → Mitigation: explicit authenticated-only rule; do not attach identity helper to guest endpoints; add/keep a guest smoke check if one exists.
- **[Risk] Null email crash on phone-only auth** → Mitigation: audit normalize/lower on email in auth response paths; add phone-only null-email test.
- **[Risk] Over-trusting social email** → Mitigation: Decision 4; tighten Facebook “email present ⇒ verified” if present.
- **[Risk] N+1 SocialIdentity queries** → Mitigation: `exists()` / single status builder reuse.
- **[Risk] Clients still hard-code email verify** → Mitigation: docs for `identity_verified` + Bangla UI example.
- **[Trade-off] Deriving social flags vs storing booleans** → Slightly more query cost; much less consistency risk.

## Migration Plan

1. Ship helper + gate replacements + auth payload in one deploy (no schema migration).
2. No data backfill: email-verified, phone-verified, and social-linked users already have the needed rows/flags.
3. Rollback: revert gates to email-only (phone/social regress; data remains valid).
4. If social→email marking is tightened, existing wrongly email-verified social users may keep `is_email_verified=True` (still identity-verified); optional cleanup is out of scope unless product asks.

## Open Questions

- None blocking. Optional follow-up: admin 360 showing `identity_verified`; whether to retrospectively clear `is_email_verified` set only from “Facebook email present.”
