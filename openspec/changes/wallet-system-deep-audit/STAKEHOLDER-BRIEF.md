# Stakeholder brief — Wallet System Deep Audit (updated)

**Change:** `openspec/changes/wallet-system-deep-audit/`  
**Full report:** `design.md`  
**Verification:** `APPLY-VERIFICATION.md`  
**Status:** Analysis complete — **no production code or data changes** in this phase.

---

## Current architecture status

BeFood’s live custody model is coherent:

| Event | Customer Wallet | Admin Wallet |
|-------|-----------------|--------------|
| Recharge completed | recharge ↑ | customer_funding ↑ |
| Meal payment | commission first, then recharge ↓ | **no change** |
| Withdraw completed | recharge ↓ | customer_withdraw ↓ |
| Referral SUCCESS | commission ↑ | referral_commission ↓ |

Local verify (dev DB): **11/11 wallets** satisfy `balance = recharge + commission`. Meal admin-credit flag loaded as **False**.

---

## Key findings to accept

1. **`ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED`** is a footgun (default already False; meal hot path no longer credits Admin). Safe to permanently disable / remove in a **future** code change — **no history rewrite, no balance migration**.
2. **Never** run `reconcile_admin_wallet_meal_payments` for cash backfill under custody accounting.
3. **Referral** can miss accrual after successful delivery (try/except); `reconcile_referral_commissions` exists but **has no dry-run and writes** — do not schedule blindly.
4. **Admin float shortage** blocks withdraw approve (rollback) and can mark commissions FAILED.

---

## Must have next (separate OpenSpec changes after acceptance)

1. Phase B: hard-disable / remove meal-payment Admin credit flag + neutralize legacy meal reconcile writes  
2. Automated wallet consistency verification + alerts  
3. Referral reconciliation monitoring (prefer dry-run first)  
4. Admin float threshold monitoring  
5. Production deploy checklist locking the custody model  

## Please decide

- [ ] Accept this analysis report  
- [ ] Authorize opening Phase B cleanup change  
- [ ] Authorize Must-have monitoring change(s)  
- [ ] After acceptance: archive `wallet-system-deep-audit`

Contact owner: share this brief + `design.md` §11–§17 with product / finance / ops.
