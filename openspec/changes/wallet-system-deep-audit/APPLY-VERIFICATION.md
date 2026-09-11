# Apply verification annex — wallet-system-deep-audit

Date: 2026-09-11  
Environment: **local / non-production** Django DB (dev workspace)  
Scope: analysis-only apply — **no application code, migrations, or production data writes** in this session.

## Spec alignment (tasks 3.1–3.4)

| Spec | Result | Evidence in design.md |
|------|--------|------------------------|
| `wallet-system-audit-report` | **PASS** | Money flows §1; locked model §13; flag analysis §12; Phase A/B/C §17; invariant §3; mutation inventory §4; ratings §9; executive §11 |
| `wallet-financial-risk-register` | **PASS** | Critical/Medium/Low §8 + §14; SAFE/RISKY table §15 |
| `wallet-improvement-roadmap` | **PASS** | Updated Must/Should/Optional §10 (flag risk, consistency, referral monitor, float, checklist; dashboard/export/refund/ledger; event-source + webhooks) |
| No code/migration/data from **this analysis change** | **PASS** | Change folder is planning/verification only. Pre-existing WIP under `wallet/` / `referrals/` / `admin_wallet/` is **out of scope** of this analysis apply and was not modified in this session. |

## Read-only command results (tasks 4.1–4.5)

### 4.1 `verify_wallet_balance_consistency`

```
OK: 11 wallet(s) satisfy the bucket invariant.
```

**Result:** PASS

### 4.2 `audit_wallet_accounting`

```
=== 1. Live provider-ref duplicates ===
OK: no pending/completed provider recharge duplicates.
=== 2. Failed provider recharges ===
Failed provider recharges with non-empty external_ref: 0
...
=== 3. Admin Wallet completed types ===
  customer_funding: 4
  inventory_purchase: 3
  referral_commission: 2
  manual_deposit: 1
Completed customer_withdraw rows: 0
...
=== Summary ===
PASS: safe to proceed with live-status uniqueness migration (this DB).
```

**Result:** PASS (local DB)

### 4.3 Meal-payment admin credit flag (loaded settings)

```
MEAL_PAYMENT_CREDIT_ENABLED= False
CUSTOMER_FUNDING_CREDIT_ENABLED= True
REFERRAL_ENABLED= True
```

**Result:** Local/runtime setting is **False** (safe).  
**Note:** This is the process settings load for this workspace — **re-check production env/secret store** before go-live ops sign-off (`.env` file itself was not printed).

### 4.4 Referral reconcile dry-run note

Command: `python manage.py reconcile_referral_commissions`

| Finding | Detail |
|---------|--------|
| `--dry-run` | **Not implemented** |
| Writes? | **Yes** — deletes FAILED commission rows then re-accrues; also backfills missing accruals |
| Action taken this session | **Did not run** (would mutate DB) |

**Recommendation for future change:** add `--dry-run` (and ideally `--no-delete`) before scheduling in production.

### 4.5 Legacy Admin `customer_payment` count (informational)

```
admin_customer_payment_completed= 0
admin_customer_funding_completed= 4
referral_commission_by_status= pending=0, success=2, failed=0, skipped=0, reversed=0
```

**Result:** No completed legacy meal cash-credit rows on this local DB. Do not delete/modify if found on production — informational only.

## Handoff status

| Task | Status |
|------|--------|
| 5.1 Stakeholder brief | Prepared: `STAKEHOLDER-BRIEF.md` |
| 5.2 Phase B cleanup change | **Blocked** until stakeholders accept |
| 5.3 Monitoring changes | **Blocked** until stakeholders accept |
| 5.4 Archive | **Blocked** until stakeholders accept |
