# Mobile checklist — identity OR rule (not AND)

Backend change: `fix-identity-verification-or-rule`.  
Related: `wallet/docs/frontend/phone-verified-wallet-mobile-impact.md`.

## Bug this fixes

Production Confirm Recharge showed:

```text
আপনার অ্যাকাউন্ট যাচাই সম্পন্ন হয়নি।
দয়া করে একটি যাচাইকৃত মাধ্যম দিয়ে অ্যাকাউন্ট নিশ্চিত করুন।
```

That toast is for **`identity_verified === false` only**.  
It was incorrectly shown when users had **either** email **or** phone verified (often because the app treated `phone_verification_required` as a hard block, or required email∧phone).

## Canonical rule

```text
identity_verified = email_verified OR phone_verified OR google OR facebook
```

Never: `email_verified AND phone_verified`.

## After login / on Confirm Recharge

1. Prefer fresh `GET /user_management/me/` (now includes `verification_status`).
2. **Allow** recharge / subscribe / orders when `verification_status.identity_verified === true`.
3. If `phone_verification_required === true` but identity is true → soft prompt to bind phone later; **do not** block Confirm Recharge.
4. Show the Bangla identity toast **only** when `identity_verified === false`.

### Example: email verified, phone not (Case 1)

```json
{
  "phone_verification_required": true,
  "verification_status": {
    "email_verified": true,
    "phone_verified": false,
    "google_verified": false,
    "facebook_verified": false,
    "identity_verified": true
  }
}
```

→ Confirm Recharge **allowed**. Soft “add phone” UX optional.

### Example: phone verified, email not (Case 2)

```json
{
  "phone_verification_required": false,
  "verification_status": {
    "email_verified": false,
    "phone_verified": true,
    "identity_verified": true
  }
}
```

→ Confirm Recharge **allowed**. Do not force email verify.

### Example: neither (Case 3)

```json
{
  "verification_status": { "identity_verified": false }
}
```

→ Show Bangla identity toast; block gated features.

## When is a mobile release mandatory?

| App behavior today | Action |
|--------------------|--------|
| Hard-blocks on `phone_verification_required` or `email && phone` | **Required** — switch to `identity_verified` |
| Already gates only on `identity_verified` from auth envelope and refreshes correctly | Optional — still adopt `/me.verification_status` for post-login refresh |
| Shows identity Bangla toast for soft phone prompt | **Required** — copy/condition fix |

## Backend smoke (already covered by tests)

- Email-only → `/me` identity true + soft phone true → recharge 200 (not identity 403)
- Phone-only → `/me` identity true → recharge 200
- Neither → recharge 403 wallet identity message
