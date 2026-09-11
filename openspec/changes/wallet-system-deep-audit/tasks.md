## 1. Report completeness (design.md)

- [x] 1.1 Document complete money flows: recharge, meal payment, withdraw, referral, Admin Wallet custody
- [x] 1.2 Document dual-bucket models, relationships, and architecture diagram
- [x] 1.3 Audit balance invariant and impossible-balance scenarios
- [x] 1.4 Produce ledger mutation inventory with file/function/purpose/risk
- [x] 1.5 Audit referral commission timing, amount base, eligibility, duplicate prevention
- [x] 1.6 Audit Admin Wallet increase/decrease paths and mismatch risks
- [x] 1.7 Review atomicity, races, double payment/commission safety
- [x] 1.8 Publish Critical / Medium / Low risk register
- [x] 1.9 Publish industry comparison ratings (architecture / safety / scalability)
- [x] 1.10 Publish Must / Should / Optional improvement roadmap
- [x] 1.11 Write executive summary with scale-readiness verdict

## 2. Production-safe update (Issues 1–6)

- [x] 2.1 Analyze `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` usage, removal safety, and data impact (§12)
- [x] 2.2 Lock final custody accounting model table (§13)
- [x] 2.3 Re-review Critical risks: silent referral, float shortage, direct balance writes (§14)
- [x] 2.4 Publish SAFE vs RISKY production change table (§15)
- [x] 2.5 Document backward-compatibility guarantees for balances and history (§16)
- [x] 2.6 Publish phased safe implementation plan A/B/C with no-history-rewrite rules (§17)
- [x] 2.7 Update Must / Should / Optional roadmap for live production (§10)

## 3. Spec alignment checks

- [x] 3.1 Confirm `wallet-system-audit-report` scenarios match design.md (including §12–§17)
- [x] 3.2 Confirm `wallet-financial-risk-register` matches Critical risk review + production safety table
- [x] 3.3 Confirm `wallet-improvement-roadmap` matches updated Must/Should/Optional lists
- [x] 3.4 Confirm this analysis phase performed no code, migration, or production data changes

## 4. Optional read-only verification (staging / replica only)

- [x] 4.1 Run `python manage.py verify_wallet_balance_consistency` on a non-production or replica DB and record pass/fail in an annex note
- [x] 4.2 Run `python manage.py audit_wallet_accounting` on the same DB and record summary
- [x] 4.3 Confirm production env has `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` unset or False (read-only config check)
- [x] 4.4 If referrals are deployed, dry-run note for `reconcile_referral_commissions` (no write unless explicitly approved in a future change)
- [x] 4.5 Informational only: count legacy Admin `customer_payment` rows if present — do not modify

## 5. Handoff

- [x] 5.1 Share updated executive summary + §12–§17 with product/finance/ops
- [ ] 5.2 Open a **separate** OpenSpec change for Phase B flag/dead-code cleanup only after acceptance
- [ ] 5.3 Open separate change(s) for Must-have monitoring (consistency / referral / float)
- [ ] 5.4 Archive or sync this analysis change when stakeholders accept the updated report
