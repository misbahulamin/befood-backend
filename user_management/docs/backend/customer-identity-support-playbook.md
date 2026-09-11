# Customer identity — support playbook (no auto-merge)

Production-safe guidance for suspected duplicate or split accounts
(email-only + phone-only for the same human).

## Do not

- Auto-merge `User` / `CustomerProfile` rows
- Rewrite customer primary keys or `public_id`
- Move or rewrite `ReferralRelationship` / commission history
- Copy wallet balances between accounts without finance sign-off
- Delete the “extra” account if it has subscriptions, deliveries, or wallet activity

## Detection

```bash
python manage.py report_customer_identity_issues --limit 100
```

Read-only. Review:

- Duplicate emails (case-insensitive)
- Verified email with null phone (should use **bind**, not anonymous phone register)
- Blank-email phone customers

## Manual triage checklist

1. Confirm both accounts belong to the same person (OTP phone + email ownership).
2. Prefer keeping the account with subscription / wallet / meal history.
3. Document both `customer_id` / `user_id` and freeze further dual login if needed.
4. Escalate to engineering for a **separate** approved merge change — not this feature’s scope.
5. For new registrations going forward: mobile must use bind after email/social; referral only when `referral_input_allowed=true`.

## Migrations

This identity-linking change ships **no** customer PK migrations. Any future merge tooling must be additive and explicitly approved.
