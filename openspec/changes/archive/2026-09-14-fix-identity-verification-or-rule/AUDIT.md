# Audit notes (apply session)

## Paths

| Path | Flags after verify | `/me` before this change | Hard gate backend |
|------|--------------------|--------------------------|-------------------|
| Email register + verify | `email_verified=true`, `phone_verified=false`, `phone_verification_required=true` | Soft flag only; **no** `identity_verified` | OR helper → allow |
| Phone OTP register | `phone_verified=true`, `email_verified=false` | Soft false; **no** `identity_verified` | OR helper → allow |
| Neither | both false | soft true | deny |

## Screenshot Bangla

```text
আপনার অ্যাকাউন্ট যাচাই সম্পন্ন হয়নি।
দয়া করে একটি যাচাইকৃত মাধ্যম দিয়ে অ্যাকাউন্ট নিশ্চিত করুন।
```

Matches FE identity-incomplete guidance from `remove-email-verification-dependency` — not email-specific API English. Likely client hard-block when it thinks identity is false (often by treating `phone_verification_required` as hard, or AND of flags), after refreshing state from `/me` without `identity_verified`.

## Grep

- No customer permission uses `phone_verification_required`.
- No `is_email_verified and is_phone_verified` hard gate found in orders/wallet.
- Gap: `/me` + extended profile omitted `verification_status`.

## Fix

Additive `verification_status` on `/me` and customer profile; soft flag unchanged; docs/mobile checklist clarify hard vs soft.
