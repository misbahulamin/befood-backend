## Context

Mobile customers who register via phone OTP hit a verification wall when submitting wallet recharge (`amount` + `transaction_id`). Product wants phone verification to fully unlock account features—including wallet funding—without requiring email.

Current backend already has:

- `create_phone_only_customer` → `is_phone_verified=True`
- `is_customer_identity_verified(user)` → true when email **or** phone **or** Google/Facebook linked
- Wallet customer views use `IsVerifiedCustomer` → calls that helper

Yet production still surfaces “verify before recharge” style UX. Likely causes (to confirm during apply):

1. **Stale gate / message mismatch** — identity 403 still uses order-placement copy (`Identity verification is required before placing an order.`), which mobile maps to Bangla “verify first for recharge.”
2. **Missing phone-only wallet API tests** — funding tests seed `is_email_verified=True` only; phone-only recharge never regression-locked.
3. **Client-side email gate** — mobile may require `email_verified` / email OTP before calling recharge even when backend would allow phone identity.
4. **Residual docs** — wallet frontend docs still say “verified customer” in an email-era sense, reinforcing wrong client assumptions.

Related prior work: `remove-email-verification-dependency` (identity helper), in-progress `phone-only-subscription-delivery-slot` (subscribe/ops email filters). This change is **wallet-funding scoped**.

## Goals / Non-Goals

**Goals:**

- Phone-OTP–verified customers can call wallet balance, history, recharge, and withdraw without email verification.
- Identity-denied responses for wallet actions use wallet-appropriate English copy (clients localize).
- Regression tests prove phone-only recharge success and fully unverified denial.
- Docs + mobile impact plan so clients stop treating email as mandatory for phone accounts.

**Non-Goals:**

- Changing admin approve/reject funding flow or Admin Wallet custody.
- Forcing phone verification on email-only accounts.
- Requiring or auto-creating email for phone users.
- Rewriting historical wallet ledger rows.
- Implementing the mobile app changes in this backend repo (plan + contract only).

## Decisions

### 1. Reuse `is_customer_identity_verified` — do not invent a wallet-only trust rule

**Choice:** Keep `IsVerifiedCustomer` / `is_customer_identity_verified` as the single trust gate for wallet endpoints.

**Why:** Avoid drift vs orders/subscriptions; phone OTP already sets `is_phone_verified`.

**Alternatives considered:** Wallet-specific “must have phone” check (rejects valid email-only users); email-optional flag on profile (redundant with existing flags).

### 2. Add wallet-scoped identity-denied message (permission or view)

**Choice:** Introduce a wallet-oriented constant (e.g. `Identity verification is required before recharging your wallet.`) and apply it on customer wallet funding/read permissions so mobile Bangla copy matches the action.

**Why:** Current shared order message confuses operators and clients.

**How (apply-time):** Prefer a thin permission subclass or `message` override used by wallet views only; do **not** change order/subscribe message text unless shared intentionally.

**Alternatives considered:** One generic “Identity verification is required.” for all features (simpler, less actionable); leave order wording (status quo, bad UX).

### 3. Audit checklist before code edits

**Choice:** During apply, grep wallet + auth paths for `is_email_verified` hard gates, email-required serializers, and docs claiming email verify for funding. Fix only real gates; leave email ownership/recovery flows alone.

**Why:** Confirms whether bug is backend gap vs client-only.

### 4. Confirm phone registration flags; no schema migration

**Choice:** Verify `create_phone_only_customer` / `verify_phone_otp` still set `is_phone_verified` + CUSTOMER group. No new columns.

**Why:** Problem is gate/docs/client alignment, not a new identity model.

### 5. Mobile impact plan (documented, separate repo)

**Choice:** Backend ships first. Mobile follow-up:

| Check | Action |
|--------|--------|
| Pre-recharge UI blocks on “email not verified” | Remove; allow when `verification_status.identity_verified` or `phone_verified` |
| Auth/`me` parsing | Prefer `identity_verified`; keep per-provider flags |
| 403 mapping | Map new wallet identity message to Bangla (e.g. verify phone / complete identity — not “verify email”) |
| Optional email prompt | Soft upsell only; never hard-block funding |

If mobile already trusts backend and has no email hard-gate, **no mandatory mobile release**—only copy polish if 403 text changes.

### 6. Spec deltas: ADDED identity requirements on wallet capabilities

**Choice:** Add explicit identity requirements under `wallet-funding` and `customer-wallet` rather than rewriting legacy “immediate manual credit” recharge wording in this change.

**Why:** Funding lifecycle already evolved via prior changes; this change only clarifies **who** may call the APIs.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Backend already allows phone users; only mobile is wrong | Audit + API tests first; still ship clearer 403 + docs + mobile plan |
| Changing 403 `detail` breaks clients matching exact English strings | Document as additive clarity; keep same HTTP status (`403`); note in frontend docs |
| Phone users without CUSTOMER group still fail | Factory already adds group; test asserts group + phone path |
| Overlap with `phone-only-subscription-delivery-slot` | Keep this change wallet-only; do not duplicate subscribe/ops filter work |
| Completely unverified social-less users gain access | No — helper still requires at least one trusted factor |

## Migration Plan

1. Deploy backend: message/docs/tests (+ any residual gate fix).
2. Smoke: phone OTP register → login → `POST /wallet/recharge/` with valid payload → expect pending funding success (not identity 403).
3. Smoke: customer with no email/phone/social verified → still `403` identity.
4. Roll out mobile plan when client gates/copy need update.
5. Rollback: revert permission message / gate commit; no DB migration.

## Open Questions

- Confirm whether production failure is backend `403` vs client-side block (capture one failing response body during apply if still reproducible).
- Whether withdraw should share the exact same message string as recharge or a shared “wallet action” wording (lean shared wallet identity message for all customer wallet endpoints).
