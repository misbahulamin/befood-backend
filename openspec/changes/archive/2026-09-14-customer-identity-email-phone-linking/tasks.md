## 1. Audit freeze & baseline

- [x] 1.1 Document current create paths that can mint `User`/`CustomerProfile` (`pending_registration` finalize, `create_phone_only_customer`, `create_social_customer`, OAuth wrappers) and mark which accept `referral_code`
- [x] 1.2 Confirm authenticated bind path (`bind_phone_otp_to_user`, bind send/verify views) already updates the same profile without referral
- [x] 1.3 Snapshot failing production scenario as regression fixtures: email register (phone null) + anonymous phone verify → two profiles (expected to fail after fix)

## 2. Identity guards (backend)

- [x] 2.1 In `verify_phone_otp`, if request carries an authenticated customer, route to bind semantics or reject with stable `USE_BIND_ENDPOINT` / equivalent — never `create_phone_only_customer`
- [x] 2.2 Ensure anonymous verify still: phone hit → login only; phone miss → create once
- [x] 2.3 Harden OAuth/email finalize paths so existing email/phone identifiers never create a second customer
- [x] 2.4 Add/adjust a small shared helper for “resolve customer by email or phone” used by create guards (no schema change required)

## 3. Referral once-per-customer (backend)

- [x] 3.1 Verify all attribution call sites only run when a new `CustomerProfile` was just created
- [x] 3.2 Ignore or reject `referral_code` on bind, existing phone login, existing social login, and existing email login with stable codes
- [x] 3.3 Keep `attribute_on_signup` immutability (`REFERRAL_ALREADY_ATTRIBUTED`) and add tests that duplicate-customer creation cannot be used to re-attribute after identity guards

## 4. Client contract signals

- [x] 4.1 Review `email-check` and `phone/check-availability` responses; add additive fields only if needed for “new vs existing → show referral?” branching
- [x] 4.2 Ensure OpenAPI descriptions state when referral is allowed vs forbidden
- [x] 4.3 Update `user_management/docs/frontend/*` with ordered flows: new email+referral→bind phone; new phone+referral; existing email; existing phone; social→bind; warn against anonymous verify after email session

## 5. Production safety (no auto-merge)

- [x] 5.1 Add read-only management command to report suspected duplicate / identity issues (no merges, no ID rewrites)
- [x] 5.2 Document manual support playbook: do not auto-merge wallets/subscriptions/referrals; escalate pairs from the report
- [x] 5.3 Confirm migrations (if any) are additive-only; no customer PK changes

## 6. Tests

- [x] 6.1 Case: register email + referral → authenticated bind phone → same profile; phone login returns same user; one referral relationship
- [x] 6.2 Case: register phone + referral → later attach/login email on same account (or documented path); same profile; no second referral
- [x] 6.3 Case: existing customer sends referral again on login/OTP → ignored/rejected; relationship unchanged
- [x] 6.4 Case: new customer registration accepts valid referral
- [x] 6.5 Case: customer with subscription/wallet binds phone and logs in with phone → same subscription/wallet
- [x] 6.6 Case: authenticated anonymous-verify attempt does not create second account
- [x] 6.7 Case: bind conflict when phone owned by another customer

## 7. Mobile handoff (docs + checklist; app repo separate)

- [x] 7.1 Publish mobile integration checklist: existence check → referral only if new; after email/social use bind OTP; never re-show referral on phone step
- [x] 7.2 List screens to change: registration (referral section), phone OTP after email, login email vs phone entry
- [x] 7.3 Align `X-Client-Type: mobile` referral rules with existing mobile-only attribution

## 8. Verification & rollout

- [x] 8.1 Run targeted auth + referral test suites
- [x] 8.2 Dry-run duplicate detection on staging/production replica
- [x] 8.3 Deploy backend first; then mobile release using bind contract; monitor new `CustomerProfile` creation rate and dual-account support tickets

### Rollout notes (ops)

- **8.2:** Run `python manage.py report_customer_identity_issues --limit 100` on a staging/production replica before/after deploy (read-only).
- **8.3:** Deploy backend first; then ship mobile using bind + `referral_input_allowed`. Monitor dual-account support tickets. No customer PK migrations in this change.
