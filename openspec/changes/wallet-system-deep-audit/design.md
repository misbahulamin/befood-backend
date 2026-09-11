## Context

BeFood is a meal-subscription platform. Customer money moves through:

| Layer | Role |
|-------|------|
| Customer `Wallet` | Dual-bucket spendable balance (`recharge_balance` + `commission_balance` = `balance`) |
| `WalletTransaction` | Customer ledger rows (credit/debit + status) |
| Admin `AdminWallet` | Platform custody float (singleton `code=platform`) |
| `AdminWalletTransaction` | Platform ledger + lifetime counters |
| `ReferralCommission` | Accrual/skip/fail/reverse records for affiliate payouts |

Primary code paths audited (read-only):

- `wallet/models.py`, `wallet/services/ledger.py`, `wallet/services/funding.py`
- `admin_wallet/models.py`, `admin_wallet/services/ledger.py`, `admin_wallet/services/ingestion.py`, `admin_wallet/services/operations.py`
- `orders/services/meal_payment.py`, `orders/services/order_delivery.py`
- `referrals/services/commission.py`, `referrals/models.py`
- Commands: `verify_wallet_balance_consistency`, `audit_wallet_accounting`, `reconcile_*`

**Constraint for this change:** analysis and planning only — no code, migration, or commit.

**Production reality (updated):** Wallet + referral are **live**. Existing customers, balances, recharge history, meal payments, and wallet transactions MUST remain unchanged by any remediation derived from this plan. No historical rewrite; no balance recalculation migrations.

---

## Goals / Non-Goals

**Goals:**

- Document complete money flows (recharge, meal pay, withdraw, referral, admin custody).
- Verify dual-bucket invariant and mutation surfaces.
- Produce Critical / Medium / Low risk register + improvement roadmap.
- Answer: *Can BeFood scale safely with this wallet accounting model?*
- **Updated:** Analyze safe removal/disable of `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` under live production.
- **Updated:** Lock the final custody accounting model and publish a production-safe implementation plan (plan-only).
- **Updated:** Refresh Must / Should / Optional roadmap for live finance hardening.

**Non-Goals:**

- No production code changes, migrations, deploys, or commits in this analysis phase.
- No redesign of referral product rules (percent, attribution) in this change.
- No live production DB remediation, balance backfill, or historical transaction edits as part of analysis.
- No schema changes that rewrite existing wallet rows.

---

## Decisions

### D1 — Treat service-layer ledger as operational source of balance truth

**Choice:** Document that **wallet row balances are the operational source of truth**, updated only through `credit_wallet` / `debit_wallet` / funding approve-reject helpers that call `_apply_credit` / `_apply_debit`. Ledger rows are append-only records with `*_after` snapshots, not independently recomputed balances.

**Why over pure event-sourced ledger:** Current code already mutates balance then inserts txn; rebuilding balance from ledger is a future control, not current runtime.

**Alternative considered:** Require sum(ledger) == balance everywhere now → large rewrite; deferred to roadmap.

### D2 — Custody accounting model for Admin Wallet

**Choice:** Document current custody model as correct intent:

- Customer **recharge completed** → Admin Wallet **credit** (`customer_funding`)
- Customer **withdraw completed** → Admin Wallet **debit** (`customer_withdraw`)
- Meal delivery debit → **does not** cash-credit Admin Wallet (flag `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` default **False**)
- Referral SUCCESS → Admin Wallet **debit** then customer commission **credit**

**Why:** Avoids double-counting (recharge + meal payment both crediting platform).

### D3 — Dual-bucket spend / withdraw rules

**Choice:** Affirm coded policy as business-correct for subscription wallets:

| Operation | Bucket strategy |
|-----------|-----------------|
| Recharge credit | `recharge` only |
| Referral commission credit | `commission` only |
| Meal payment debit | `commission_first` then recharge |
| Withdraw debit | `recharge_only` |
| Commission reversal | `commission_only` |

**Why commission-first on meals:** Commission is meal-spendable but not withdrawable; consuming it first protects float and prevents commission→cash-out via withdraw.

### D4 — Analysis deliverable lives in this design + specs

**Choice:** Full audit findings are captured here; specs define acceptance criteria for the report/risk register/roadmap; tasks are verification/documentation checkboxes only (no app code).

---

## 1. Complete Money Flow Analysis

### 1.1 System overview

```text
External payment (bKash/Nagad/Bank)
        │
        ▼
 Customer funding request (WalletTransaction pending)
        │ approve
        ▼
 Customer Wallet (recharge_balance ↑, balance ↑)
        │ same atomic
        ▼
 Admin Wallet (custody ↑ customer_funding)

        ┌─────────────────────────────────────┐
        │  Meal delivered                     │
        │  → debit customer (commission first)│
        │  → NO admin cash credit (default)   │
        │  → maybe referral commission:       │
        │      Admin ↓ → Referrer commission↑ │
        └─────────────────────────────────────┘

 Customer withdraw request
        │ reserve: recharge_balance ↓ (pending)
        │ approve: Admin Wallet ↓ (customer_withdraw)
        │ reject:  recharge_balance restored
```

### 1.2 Customer Recharge Flow

```text
Customer
  → POST funding request (payment_method + provider txn id)
  → WalletTransaction PENDING (credit, type=recharge)  [NO balance change]
  → Admin reviews
      ├─ approve → credit recharge_balance + balance; status COMPLETED;
      │            Admin Wallet credit customer_funding; invoice; notify
      └─ reject  → status FAILED; balance unchanged
```

| Concern | Detail |
|---------|--------|
| Where money “created” | Only on **approve** (or legacy immediate `recharge_wallet`); pending does not create spendable funds |
| Tables | `wallet_wallet`, `wallet_wallettransaction`; Admin: `admin_wallet_adminwallet`, `admin_wallet_adminwallettransaction` |
| Services | `request_recharge` → `approve_recharge` / `reject_recharge`; sync via `credit_from_customer_recharge` |
| Statuses | `pending` → `completed` \| `failed`; `cancelled` exists on model but funding paths use `failed` for reject |
| Idempotency | Per-wallet `idempotency_key`; live unique on `(method, external_ref)` for pending/completed provider recharges |
| Gateway note | `complete_pending_credit` / `fail_pending` reserved for future webhooks; current product is **manual verification** |

### 1.3 Meal Payment Flow

```text
mark_delivery → DELIVERED
  → charge_delivered_meal (same atomic as status)
  → debit_wallet type=PAYMENT, strategy=commission_first
  → attach wallet_transaction, payment_status=CHARGED, charged_amount
  → (best-effort) Onahar + referral hooks
```

| Question | Answer |
|----------|--------|
| Which balance first? | **Commission first**, then recharge |
| Why? | Commission is meal-only; depleting it first maximizes withdrawable recharge left for the customer and prevents commission leakage via cash-out |
| Amount source | Published slot `final_meal_price_snapshot` (not package average), unless emergency flag `MEAL_DELIVERY_CHARGE_USE_ORDER_AVERAGE` |
| Admin Wallet | No credit on meal pay (custody already taken at recharge) |
| Double charge | Idempotency key `meal-delivery:{delivery.public_id}` + delivery `CHARGED` short-circuit |

### 1.4 Withdrawal Flow

```text
request_withdraw
  → validate amount ≤ recharge_balance
  → immediate debit recharge_only; txn PENDING
approve_withdraw
  → status COMPLETED + Admin debit customer_withdraw (rollback if float short)
reject_withdraw
  → credit recharge back; status FAILED
```

| Check | Result |
|-------|--------|
| Only recharge withdrawable? | **Yes** (`STRATEGY_RECHARGE_ONLY` / `withdrawable_balance`) |
| Commission accidentally withdrawable? | **No** on coded paths |
| Negative balance? | Blocked by insufficient checks + `MinValueValidator(0)` on model; race mitigated by `select_for_update` |

---

## 2. Wallet Database Architecture Review

### Models

| Model | Purpose | Key fields | Responsibility |
|-------|---------|------------|----------------|
| `Wallet` | Customer balance snapshot | `balance`, `recharge_balance`, `commission_balance`, `currency`, `status` | Denormalized spendable totals; 1:1 customer |
| `WalletTransaction` | Customer ledger | type, direction, amount, status, method, `*_after`, idempotency, external_ref, invoice | Audit trail + funding workflow state |
| `AdminWallet` | Platform float | `balance`, lifetime counters | Custody + ops cash |
| `AdminWalletTransaction` | Platform ledger | type/direction/amount/status, FKs to order/delivery/customer/customer txn | Custody + expense + referral |
| `AdminWalletAuditLog` | Manual ops audit | action, previous/new balance, actor | Extra trail for deposits/withdrawals/expenses |
| `ReferralCommission` | Affiliate accrual | meal_price, %, amount, status, FKs to admin/customer txns | Commission lifecycle |
| `ReferralRelationship` | Attribution | referrer, referred (1:1) | Who earns on whose meals |

There is **no separate Recharge/Withdrawal table** — funding is modeled as `WalletTransaction` rows (`type=recharge|withdraw`, often `status=pending` until admin action).

### Relationship diagram

```text
CustomerProfile
      │ 1:1
      ▼
   Wallet
      │ 1:N
      ▼
 WalletTransaction ◄──── AdminWalletTransaction (optional FK)
                              │
                              ▼
                         AdminWallet (platform)

OrderDelivery ──FK──► WalletTransaction (meal charge)
OrderDelivery ──1:N──► ReferralCommission (unique non-manual per delivery)
ReferralCommission ──FK──► WalletTransaction + AdminWalletTransaction
```

---

## 3. Wallet Balance Calculation Audit

### Invariant

```text
balance == recharge_balance + commission_balance
```

Enforced in `_apply_credit` / `_apply_debit` via `assert_wallet_invariant`. Ops command: `python manage.py verify_wallet_balance_consistency`.

### How updates work

1. Lock wallet `select_for_update`
2. Mutate bucket(s)
3. Recompute `balance = recharge + commission`
4. Assert invariant
5. Save three fields
6. Create ledger row with after-snapshots

### Inconsistency scenarios

| Scenario | Risk |
|----------|------|
| All production money paths via ledger helpers | **Low** for `1000 ≠ 700+200` style drift |
| Direct ORM / Django admin / tests setting `wallet.balance` alone | **Medium** — tests do this; admin misuse could break invariant |
| Failed/cancelled pending recharge | Balance unchanged (correct) |
| Pending withdraw | Balance already reduced (reservation); reject restores recharge |
| Partial failure after balance save before txn insert | Mitigated by `@transaction.atomic` wrapping credit/debit |
| Historical wallets before dual-bucket migration | Migration backfills `recharge_balance = balance`, `commission_balance = 0` |

**Verdict:** The impossible example (`balance=1000`, buckets `700+200`) **should not occur** on service paths; it **can** occur if balances are written outside ledger helpers. Guardrail exists but is not a DB CHECK constraint.

---

## 4. Ledger System Audit

### Source of truth?

| Question | Answer |
|----------|--------|
| Is ledger the source of truth? | **No** — balances are denormalized on `Wallet` / `AdminWallet` |
| Is ledger immutable? | Practically append-oriented; status transitions on same row for funding (pending→completed/failed); not full event-sourcing |
| Balance updates from multiple places? | **Concentrated** in ledger + funding services; meal/referral call those |

### Mutation inventory (production paths)

| File | Function | Purpose | Risk |
|------|----------|---------|------|
| `wallet/services/ledger.py` | `credit_wallet` | Generic credit + ledger | Low (locked, atomic, invariant) |
| `wallet/services/ledger.py` | `debit_wallet` | Generic debit + ledger | Low |
| `wallet/services/ledger.py` | `recharge_wallet` / `withdraw_wallet` | Immediate manual funding + admin sync | Medium if still exposed alongside request/approve flow |
| `wallet/services/ledger.py` | `complete_pending_credit` / `fail_pending` | Gateway seams | Low until wired |
| `wallet/services/funding.py` | `request_recharge` | Pending credit, no balance | Low |
| `wallet/services/funding.py` | `request_withdraw` | Reserve recharge | Low |
| `wallet/services/funding.py` | `approve_recharge` | Credit + admin custody | Low if atomic holds |
| `wallet/services/funding.py` | `reject_recharge` | Fail only | Low |
| `wallet/services/funding.py` | `approve_withdraw` | Complete + admin debit | Medium if float race (handled by rollback) |
| `wallet/services/funding.py` | `reject_withdraw` | Restore recharge | Low |
| `orders/services/meal_payment.py` | `charge_delivered_meal` | Meal debit | Low (idempotent) |
| `referrals/services/commission.py` | `credit_referral_commission_for_delivery` | Admin debit + commission credit | Medium — outer hook swallows exceptions |
| `referrals/services/commission.py` | `reverse_*` / `manual_adjust_*` | Clawback / manual | Medium (manual keys time-based) |
| `admin_wallet/services/operations.py` | deposit/withdraw/expense/adjust/inventory | Ops float | Medium (human error; audit log helps) |
| `admin_wallet/services/ingestion.py` | recharge/withdraw/meal sync | Custody bridge | Low (idempotent keys) |

---

## 5. Referral Commission Financial Audit

### Flow

```text
A refers B (ReferralRelationship)
B meal marked DELIVERED
  → meal charged (charged_amount set)
  → credit_referral_commission_for_delivery
      → require delivered
      → unique non-manual commission per delivery
      → require active subscription for referrer AND referred
      → amount = ROUND_HALF_UP(charged_amount * REFERRAL_COMMISSION_PERCENT / 100)
      → Admin Wallet debit REFERRAL_COMMISSION
      → Referrer wallet credit commission bucket
```

| Topic | Finding |
|-------|---------|
| When generated? | **After** delivery mark, after meal charge attempt, same request; only if status is DELIVERED |
| Before vs after delivery | After delivery (and after charge in happy path) |
| Duplicate prevention? | DB unique on `order_delivery` for non-manual non-reversal; idempotency keys on wallet/admin txns; early return if existing non-PENDING |
| Base amount field | `OrderDelivery.charged_amount` (post-charge). If null → treated as 0 → skip/small |
| Discount/coupon | Not a separate wallet concept; charge uses published slot final price (or emergency average). Commission follows **charged** amount |
| Referrer eligibility | Active meal subscription required else SKIPPED `REFERRER_INACTIVE` |
| Referred eligibility | Active subscription required else SKIPPED `REFERRED_INACTIVE` |
| Meal consumed | Delivery must be DELIVERED; charge should have run first |
| Admin float short | Commission marked FAILED `ADMIN_FLOAT_INSUFFICIENT` (fail closed for payout) |
| Hook resilience | `order_delivery` wraps referral in try/except — **delivery + meal charge commit even if referral raises**; reconcile command exists |

**Business correctness:** Reasonable for subscription affiliate (pay on consumed meal, both parties active, non-withdrawable commission, platform-funded). Main gap is **silent failure** of accrual vs hard fail of meal charge.

---

## 6. Admin Wallet Audit

| Event | Admin Wallet |
|-------|--------------|
| Customer recharge completed | **↑** `customer_funding` |
| Customer withdraw completed | **↓** `customer_withdraw` |
| Meal payment | **No change** (default) |
| Referral SUCCESS | **↓** `referral_commission` |
| Referral reverse / clawback | **↑** `referral_commission_reversal` |
| Manual deposit / expense / inventory | Per ops APIs |
| Customer refund type | Model supports `customer_refund` debit; **meal refund ledger path not fully productized** in audited meal flow |

**Accounting mismatches to watch:**

1. Enabling `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` **double-counts** revenue vs custody.
2. Referral SUCCESS without enough float → FAILED commission while meal already paid (liability backlog).
3. Lifetime counters are denormalized; drift possible if historical rows adjusted outside ledger.
4. Platform float can block customer withdraws and commissions even when customer recharge_balance is fine — correct for custody, but ops must fund float.

---

## 7. Transaction Safety Review

| Concern | Assessment |
|---------|------------|
| Atomic blocks | Present on credit/debit, funding approve/reject, meal charge, commission accrual |
| `select_for_update` | Used on wallet, funding txn, delivery, commission |
| Double meal payment | Prevented by idempotency + payment_status |
| Double commission | Prevented by unique constraint + idempotency; concurrent create hits IntegrityError → reload |
| Double admin custody credit | Idempotency `customer-recharge:{public_id}` |
| Race two delivery completes | Status terminal + locks; second mark no-ops |
| Referral after swallowed exception | Possible **missed** commission → reconcile job needed |
| Pending withdraw + concurrent meal | Both lock wallet; commission-first may leave insufficient recharge for other ops — serialized correctly |

---

## 8. Business Rule Gap Analysis (Risk Register)

### Critical

| Risk | Impact | Solution (plan) |
|------|--------|-----------------|
| Referral hook swallows errors → unpaid commissions at scale | Affiliate trust + understated liability | Fail-visible metrics + mandatory reconcile cron; optionally fail-open to FAILED row always |
| Admin float exhaustion blocks withdraws/commissions | Customer payouts stuck; commissions FAILED | Float monitoring alerts; ops funding SOP; dashboard |
| Accidental enable of meal-payment admin credit **or** running legacy `reconcile_admin_wallet_meal_payments` write | Double revenue in Admin Wallet | Keep flag false; forbid legacy meal cash backfill; later remove/hard-disable code (§12) |
| Balances writable outside ledger (admin/scripts) | Broken invariant / silent loss | Restrict admin fields; DB CHECK; nightly `verify_wallet_balance_consistency` |

### Medium

| Risk | Impact | Solution |
|------|--------|----------|
| No continuous ledger↔balance reconciliation | Drift undetected until incident | Scheduled reconcile: sum completed credits/debits vs balance |
| Refund / reversal of meal charges incomplete as first-class flow | Ops manual adjustments; error-prone | Explicit refund debit/credit pairing + admin custody rules |
| Dual immediate vs request/approve funding APIs | Confusion / wrong path in clients | Document single public path; deprecate immediate if unused |
| Manual referral adjust keys use timestamps | Weak idempotency under retry storms | Stable client-supplied idempotency keys |
| Commission based on `charged_amount` if charge skipped (feature flag off) | 0 commission or wrong base | Guard: skip accrual if not CHARGED |

### Low

| Risk | Impact | Solution |
|------|--------|----------|
| `cancelled` status underused vs `failed` | Reporting ambiguity | Normalize glossary in finance reports |
| Counter fields vs ledger sum | Dashboard drift | Period totals from ledger, not only counters |
| Gateway seams unused | Future integration bugs | Spec webhook state machine before go-live |

---

## 9. Industry Standard Comparison

| Practice | BeFood today | Gap |
|----------|--------------|-----|
| Ledger-based accounting | Hybrid (balance + ledger) | No runtime rebuild-from-ledger |
| Immutable transactions | Mostly append; funding mutates status | Acceptable for workflow; not pure immutable |
| Balance snapshot | `*_after` on customer + admin txns | Good |
| Audit trail | Strong for admin manual ops; customer funding review fields | Good |
| Reconciliation | Commands exist; not continuous productized | Needs ops cadence |
| Refund handling | Types exist; meal refund weak | Gap |
| Commission accounting | Explicit types + eligibility + uniqueness | Strong for stage |

**Ratings**

| Dimension | Score |
|-----------|-------|
| Wallet Architecture | **7.5 / 10** |
| Accounting Safety | **7.0 / 10** |
| Scalability | **6.5 / 10** |

Architecture is appropriate for a food-subscription wallet with custody + non-withdrawable rewards. Scalability score reflects ops/reconciliation maturity and float/commission failure visibility more than raw schema limits.

---

## 10. Missing Features Recommendation (Updated)

### Must have now

1. **Disable/remove double-count risk** from `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` (config harden now; code cleanup in a future apply change — see §12)  
2. Automated / scheduled `verify_wallet_balance_consistency` + alert on failure  
3. Referral commission reconciliation monitoring (`reconcile_referral_commissions` + FAILED/float alerts)  
4. Admin Wallet float monitoring (threshold alerts for withdraw + commission)  
5. Production deploy checklist (custody model flags, never run legacy meal-payment credit reconcile for cash backfill)

### Should have later

1. Finance dashboard (custody in/out, commission liability, float)  
2. Transaction export (CSV/audit export)  
3. Refund/reversal workflow (meal charge reverse with bucket-aware restore)  
4. Continuous ledger↔balance reconciliation (customer + admin)

### Optional

1. Event-sourced wallet rebuild  
2. Provider webhook automation (pending→complete recharge seams)  
3. Multi-currency / commission escrow hold periods  

---

## 11. Final Business Report (Executive Summary — Updated)

### 1) Current wallet architecture status

**Good:**

- Live custody model is coherent: recharge credits platform float; meal debit only hits customer wallet; withdraw debits float; referral pays from float into commission bucket.
- Dual-bucket rules (commission-first meal spend; recharge-only withdraw) match the stated business model.
- Hot path for meal delivery **no longer calls** `credit_from_meal_payment` (already removed from `charge_delivered_meal`).
- Concurrency controls and idempotency are strong on funding and meal charge.

**Problem:**

- Legacy meal→Admin credit **flag + reconcile command** still exist — misconfiguration/ops misuse can double-count.
- Referral accrual can fail after successful delivery without blocking delivery (possible missed commission until reconcile).
- Continuous monitoring (consistency / float / referral) is not yet productized as Must-have ops.

**Risk:**

- Primary live risks are **config/ops mistakes** and **under-observed commission/float failures**, not rewriting customer balances on the happy path.

### Scale readiness answer

**Conditionally yes** — architecture is production-capable. Finance safety at scale depends on executing the Must-have ops controls and safely retiring the legacy meal-credit footgun **without** touching historical data.

### Recommended Improvements

**Immediate (plan → future apply):**

1. Harden / remove meal-payment Admin credit risk (§12).  
2. Automate consistency + referral reconcile + float alerts.  
3. Deploy checklist forbidding legacy meal cash backfill under custody accounting.

**Future:**

1. Finance dashboard + export.  
2. Formal refund/reversal ledger.  
3. Continuous ledger reconciliation; optional webhook recharge.

---

## 12. Issue 1 — `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` removal analysis

### Where used today

| Location | Role |
|----------|------|
| `core/settings/base.py` | Env-backed setting, **default `False`**, commented as deprecated |
| `admin_wallet/services/ingestion.py` → `meal_payment_credit_enabled()` | Gate |
| `admin_wallet/services/ingestion.py` → `credit_from_meal_payment()` | Legacy cash credit (early-return when flag false) |
| `admin_wallet/management/commands/reconcile_admin_wallet_meal_payments.py` | LEGACY backfill command calling `credit_from_meal_payment` |
| Tests / docs | Assert/document flag false under custody |

**Not used on live meal hot path:** `orders/services/meal_payment.py` does **not** call `credit_from_meal_payment`.

### Is removal safe?

**Yes, for production money**, if done as config/code cleanup without data rewrites:

- Default is already `False` → current behavior matches desired model.
- Removing the flag or hardcoding disabled changes **no customer balances**.
- Historical `AdminWalletTransaction` rows of type `customer_payment` (if any from pre-custody era) MUST be **left untouched**.

### Production impact

| Action | Customer wallet | Admin wallet balance now | History |
|--------|-----------------|--------------------------|---------|
| Keep flag false | None | None | None |
| Remove setting + hard-disable function | None | None (same as false) | None |
| Accidentally set flag true + run live credit path | None on customers | **Would create new admin credits** (double-count) | New rows only |
| Run `reconcile_admin_wallet_meal_payments` without dry-run while flag true | None | **Dangerous new credits** | New rows |

### Migration needed?

**No DB migration required** to disable/remove the flag.  
Any future code cleanup is app-only. **Do not** migrate/update historical `customer_payment` rows.

### Preferred safe solution (phased)

1. **Now (ops, zero code):** Ensure production `.env` has flag absent or `False`; checklist forbids enabling it; never run meal-payment reconcile for cash backfill.  
2. **Next apply change (safe code):** Remove setting (or force `False`), make `credit_from_meal_payment` always no-op or delete callability, make `reconcile_admin_wallet_meal_payments` refuse to write (or delete command) under custody mode.  
3. **Never:** rewrite historical admin/customer transactions or recalculate balances.

**Verdict:** Dead-risk cleanup is **SAFE**; historical data stays immutable.

---

## 13. Issue 2 — Final accounting model (locked)

Confirmed as the **final** business contract:

| Event | Customer Wallet | Admin Wallet |
|-------|-----------------|--------------|
| Recharge completed | `recharge_balance` **+** (and `balance` +) | `customer_funding` **+** |
| Meal payment | Debit **commission first**, then recharge | **NO CHANGE** |
| Withdraw completed | `recharge_balance` **−** | `customer_withdraw` **−** |
| Referral SUCCESS | `commission_balance` **+** | `referral_commission` **−** |

This matches current intended code paths under custody accounting and MUST remain the deploy checklist contract.

---

## 14. Issue 3 — Critical risk review (plan-only)

### Critical Risk 1 — Silent referral failure

| Question | Finding |
|----------|---------|
| After delivery success, if referral fails? | Meal charge + delivery status already committed; referral wrapped in try/except → delivery **not** rolled back |
| Failed tracking? | In-path `AdminInsufficientFundsError` → `ReferralCommission` status **FAILED**; unexpected exceptions may log only (no row) |
| Reconcile command? | **Yes** — `reconcile_referral_commissions` |
| Missed money chance? | **Yes** for referrer commission (not customer meal charge); underpayment until reconcile |

**Recommendation (plan only):** metrics on referral exceptions; cron reconcile SLA; optionally persist FAILED on unexpected errors; alert on FAILED/`ADMIN_FLOAT_INSUFFICIENT`. No production code in this phase.

### Critical Risk 2 — Admin float shortage

| Path | Behavior | Customer impact |
|------|----------|-----------------|
| Withdraw approve | Admin debit fails → **full atomic rollback**; withdraw stays pending | Funds already reserved from recharge; payout delayed until float topped up |
| Referral accrual | Admin debit fails → commission **FAILED**, no customer credit | Referrer unpaid; meal already charged |
| Meal payment | Does not debit admin | Unaffected |

**Recommendation:** float threshold alerts; ops SOP to fund platform wallet before commission/withdraw backlogs grow.

### Critical Risk 3 — Direct wallet balance modification

| Surface | Finding |
|---------|---------|
| Services | Balance changes via `_apply_credit` / `_apply_debit` then save three fields — correct |
| Django admin `Wallet` | `balance` is **readonly**; dual-bucket fields not in fieldsets (good today) |
| Tests / scripts | Some tests assign `wallet.balance` directly — not production path but proves ORM can bypass |
| Goal | All production money through ledger/service layer only |

**Recommendation (plan only):** keep admin readonly; add dual-bucket fields as readonly if exposed; forbid raw balance scripts; nightly invariant verify; optional DB CHECK later (separate change, carefully).

---

## 15. Issue 4 — Production safety table

| Change | Risk | Production Impact | Recommendation |
|--------|------|-------------------|----------------|
| Ensure flag false / env checklist | **SAFE** | None | Do now |
| Docs update (custody model) | **SAFE** | None | Do in future docs PR |
| Remove setting + hard-disable meal credit code | **SAFE** (app-only) | None if behavior stays false | Future apply change |
| Disable/delete legacy meal reconcile write path | **SAFE** | Prevents ops double-count | Future apply change |
| Schedule verify/reconcile/monitoring | **SAFE** if read-only or additive FAILED rows only | Ops visibility | Must-have follow-up |
| Wallet model field add/rename | **RISKY** | Migration + client risk | Avoid unless additive & tested |
| Rewrite historical transactions | **RISKY** | Accounting break | **Forbidden** |
| Balance recalculation migration | **RISKY** | Customer trust / money errors | **Forbidden** |
| Enable meal credit flag / run meal reconcile write | **CRITICAL** | Admin double-count | **Forbidden** under custody |

---

## 16. Issue 5 — Backward compatibility

| Asset | Required after any remediation |
|-------|--------------------------------|
| Customer `balance` / buckets | **Identical** for untouched customers |
| Completed recharge / withdraw / payment / referral rows | **Unchanged** |
| Admin historical ledger | **Unchanged** (including any legacy `customer_payment` rows) |
| Public IDs / invoice numbers | **Stable** |

Example: before `balance=1000` → after cleanup still `balance=1000`. Remediation is configuration/code surface only, not data mutation.

---

## 17. Safe implementation plan (future apply — not this phase)

### Phase A — Ops only (immediate)

1. Confirm production `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED=False` (or unset).  
2. Deploy checklist: custody model locked (§13); forbid enabling meal credit; forbid non-dry-run meal reconcile.  
3. Run read-only `verify_wallet_balance_consistency` / `audit_wallet_accounting` on replica; record results.

### Phase B — Safe code cleanup (separate OpenSpec apply)

1. Remove or hard-disable meal payment admin credit setting/function.  
2. Neutralize legacy meal reconcile command writes.  
3. Update backend docs.  
4. **No** data migrations; **no** historical updates; tests assert meal path never credits admin.

### Phase C — Monitoring (separate apply)

1. Automate consistency verify + alerts.  
2. Automate referral reconcile + FAILED/float alerts.  
3. Admin float threshold monitoring.

### Data safety rules (non-negotiable)

- Do not update existing customer balances.  
- Do not modify existing transaction history.  
- Do not “fix” accounting by rewriting rows.  
- Prefer additive observability over corrective money scripts.

---

## Risks / Trade-offs (for this analysis change)

- [Analysis based on current working tree] → Re-validate exact production commit/config before Phase B.  
- [Ratings are expert judgment] → Use for prioritization, not regulatory sign-off.  
- [No production DB sampling in this phase] → Phase A replica checks before claiming zero drift.  
- [Removing dead code later] → Must keep behavior identical to flag=false; ship behind review + tests.

## Migration Plan

**This analysis change:** N/A (no migrations).  

**Future Phase B cleanup:** app-only preferred; **no** data migration. If a migration is ever proposed for unrelated reasons, it MUST be additive/backward compatible and MUST NOT recalculate balances or rewrite ledger history.

## Open Questions

1. Are immediate `recharge_wallet` / `withdraw_wallet` APIs still customer-facing in production, or only request/approve?  
2. What is the target SLA for FAILED referral commissions (`ADMIN_FLOAT_INSUFFICIENT`)?  
3. Should meal refunds restore recharge vs commission proportionally to original debit split (metadata does not yet store split amounts)?  
4. Will commission ever become partially withdrawable?  
5. Do any production Admin Wallet rows of type `customer_payment` still exist from the pre-custody era (informational only — do not delete)?
