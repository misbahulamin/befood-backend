## Context

Analysis date baseline (local repo after `git fetch`):

| Ref | Tip | Notes |
|-----|-----|-------|
| `origin/main` | `fc02e9b` | Includes PRs #1–#3 from `production-hotfix` (live EC2 baseline) |
| Local `main` | `fdfc184` | **Stale** — behind `origin/main` by hotfix merges |
| `production-hotfix` | `8983405` | Content already on `origin/main` (merge commits differ only) |
| `unfinished-features` | `135e5e7` | **Local-only**; 1 WIP commit on top of `fdfc184` |

Merge-base of `origin/main` ↔ `unfinished-features`: `fdfc184`.

Divergence:

- `origin/main` only: **6 commits** (3 hotfix merge PRs + hotfix content)
- `unfinished-features` only: **1 commit** — `WIP: referral and wallet features unfinished`

Existing design intent for referral already lives on UF under `openspec/changes/referral-affiliate-commission-system/` (tasks largely marked done in WIP). This change’s job is **safe integration planning**, not redesigning referral product rules.

## Goals / Non-Goals

**Goals:**

- Complete conflict / wallet / migration risk report before any merge.
- Recommend a merge strategy that preserves production wallet accounting.
- Provide a step-by-step integration command plan and conflict resolution order.
- Define verification gates (migrate, verify wallets, tests) before enabling accrual.

**Non-Goals:**

- No code edits, merges, commits, or deploys in the analysis phase.
- No redesign of referral product rules (codes, 5%, mobile-only attribution).
- No production DB writes as part of analysis.

---

## Branch Difference Analysis

### Overlap files (changed on BOTH sides since merge-base)

These will produce real merge conflicts (`git merge-tree` confirmed “changed in both”):

| File | Conflict probability | Why |
|------|----------------------|-----|
| `wallet/models.py` | **HIGH** | Main: narrow provider-ref unique to live statuses. UF: dual buckets + commission txn types. Both edit same model/constraint area; UF **missing** main’s `status__in=['pending','completed']`. |
| `wallet/services/funding.py` | **HIGH** | Main: live-status `_provider_ref_taken` + `maybe_resume_after_wallet_credit` on approve. UF: bucket-aware withdraw/approve/reject. Must keep **both**. |
| `wallet/api/serializers.py` | **HIGH** | Main: `meal_service_restored`. UF: bucket fields + `withdrawable_balance`. |
| `wallet/docs/backend/customer-wallet.md` | MEDIUM | Docs diverge; rewrite from integrated behavior. |
| `user_management/models.py` | **LOW–MEDIUM** | Main: default city `Chittagong`. UF: pending registration referral snapshot fields. Different regions — easy manual combine. |
| `core/urls.py` | **LOW–MEDIUM** | Main: web dashboard mount. UF: referrals mounts. Adjacent additive paths. |
| `db.sqlite3` | **N/A** | Binary junk — **discard both; never merge**. |

### Migration number collision (critical)

| Branch | `wallet/migrations/0004_*` |
|--------|----------------------------|
| `origin/main` | `0004_live_status_provider_recharge_ref_unique.py` (already on production path) |
| `unfinished-features` | `0004_dual_bucket_balances.py` (dual buckets + commission types + data migrate) |

Both depend on `0003_wallet_txn_invoice_number`. Django **cannot** apply two different `0004`s. UF also has `0005_referral_affiliate_system.py` depending on UF’s `0004`.

**Required fix:** On integration branch, keep main’s `0004`, renumber dual-bucket migration to `0005_…`, renumber UF helptext alter to `0006_…` (or fold helptexts into the dual-bucket migration).

### Per-file conflict report (critical paths)

#### `wallet/models.py`

- **main:** Adds `status__in=['pending','completed']` to `wallet_txn_unique_provider_recharge_ref`.
- **unfinished-features:** Adds `recharge_balance`, `commission_balance`, `withdrawable_balance` property; txn types `referral_commission` / `referral_commission_reversal`; `recharge_balance_after` / `commission_balance_after`. Constraint still **excludes** failed/cancelled only via empty-ref + method filters — **does not** include live-status narrowing.
- **Conflict probability:** HIGH
- **Keep:** Both — dual buckets **and** live-status unique constraint.

#### `wallet/services/funding.py`

- **main:** Provider-ref uniqueness check filters pending/completed; approve attaches meal-service resume flag.
- **unfinished-features:** Withdraw/approve/reject use `_apply_debit` / `_apply_credit` on recharge bucket + after snapshots.
- **Conflict probability:** HIGH
- **Keep:** Both behaviors; discard neither.

#### `wallet/services/ledger.py`

- **main:** Unchanged vs merge-base.
- **unfinished-features:** Full bucket strategies (`commission_first` for meal payment, `recharge_only` withdraw, `commission_only` reversal).
- **Conflict probability:** LOW (take UF; no main edit)
- **Keep:** UF ledger; retest meal payment + withdraw against production scenarios.

#### `wallet/migrations/*`

- **Conflict probability:** HIGH (duplicate `0004` number)
- **Keep:** Main `0004`; resequence UF migrations after it.

#### `admin_wallet/models.py` + `0005_referral_commission_types.py`

- **main:** No model type edits in hotfix set (serializers/queries/docs/tests only).
- **unfinished-features:** Adds `REFERRAL_COMMISSION` / `REFERRAL_COMMISSION_REVERSAL` and migration `0005`.
- **Conflict probability:** LOW
- **Keep:** UF additive types.

#### `user_management/models.py` + `0021_referral_affiliate_system.py`

- **main:** Default city change only.
- **unfinished-features:** Pending registration referral fields + migration `0021` (no number clash with main — main has no `0021`).
- **Conflict probability:** LOW–MEDIUM (model file) / LOW (migration)
- **Keep:** Both city default and referral fields.

#### `orders/services/order_delivery.py`

- **main:** Unchanged.
- **unfinished-features:** Onahar-style try/except hook to `credit_referral_commission_for_delivery` after deliver charge.
- **Conflict probability:** LOW
- **Keep:** UF hook; confirm still after charge path on current main.

#### `core/urls.py` / `core/settings/base.py`

- **urls:** Additive mounts on both sides — combine.
- **settings:** UF adds `referrals` app + `REFERRAL_*` settings (main unchanged) — take UF.

#### Auth / registration touchpoints (UF only)

- `user_management/services/{customer_factory,phone_otp,google_oauth,facebook_oauth,pending_registration}.py`
- `user_management/api/{serializers,views}.py`
- Main did not edit these in the hotfix window → **LOW** conflict if ported onto latest main, but must re-test OAuth/OTP flows that hotfix did not change.

---

## Referral Feature Impact Analysis

### Components on `unfinished-features`

| Area | Location |
|------|----------|
| Models | `referrals/models.py` — `ReferralProfile`, `ReferralRelationship`, `ReferralCommission`, `ReferralValidationEvent` |
| Services | `attribution`, `codes`, `commission`, `eligibility`, `events`, `queries` |
| APIs | `referrals/api/{views,serializers,urls,web_urls,openapi}.py` |
| Migrations | `referrals/migrations/0001_referral_affiliate_system.py` |
| Wallet integration | dual buckets; commission credit via `ledger`; Admin Wallet debit types |
| Commission logic | `% of charged meal` on `delivered`; skip if inactive sub; idempotent per delivery |
| Ops commands | `backfill_referral_profiles`, `reconcile_referral_commissions`, `verify_wallet_balance_consistency` |
| Tests/docs | `referrals/tests/*`, backend + mobile frontend docs |
| OpenSpec | `openspec/changes/referral-affiliate-commission-system/` |

### Dependencies on existing systems

| System | How referral depends |
|--------|----------------------|
| User / `CustomerProfile` | ReferralProfile 1:1; relationship referrer/referred |
| Pending registration | Snapshot fields for email finalize re-check |
| Mobile auth (OTP/social) | Attribution only on mobile create paths |
| `CustomerSubscription` / `get_active_subscription` | Code usability + commission eligibility |
| `OrderDelivery` / `mark_delivery` | Accrual trigger after meal charge |
| Customer `Wallet` / ledger | Commission bucket credit; meal debit commission-first |
| Admin Wallet ledger | Expense debit + reversal credit |
| Config | `REFERRAL_ENABLED`, percent, link base URL |

---

## Wallet Conflict Analysis (Most Important)

### Same files modified?

Yes — `wallet/models.py`, `wallet/services/funding.py`, `wallet/api/serializers.py`, docs, management package `__init__` paths. Main also added `audit_wallet_accounting`; UF added `verify_wallet_balance_consistency` — both commands should remain.

### Same tables/models?

Yes — `Wallet`, `WalletTransaction`. UF **adds columns**; main **alters UniqueConstraint condition** (no new columns). Compatible if model + migrations compose correctly.

### Migration conflict chance?

**HIGH** — duplicate `wallet.0004` leaf names. Production that already applied main’s `0004` cannot apply UF’s `0004` as-written.

### Production data break risk?

| Risk | Level | Notes |
|------|-------|-------|
| Dual-bucket data migrate (`recharge=balance`, `commission=0`) | MEDIUM | Safe if invariant holds; fails loud on drift |
| Losing live-status provider-ref uniqueness | **HIGH** if UF wins blindly | Allows ref reuse after failed/cancelled incorrectly blocked — production deliberately narrowed this |
| Losing meal-service resume on approve | **HIGH** if UF funding wins blindly | Operators lose auto-resume after recharge approve |
| Commission withdrawable by mistake | **HIGH** if buckets incomplete | Product requirement: commission not withdrawable |
| Admin float shortfall during accrual | MEDIUM | Commission path marks `failed`; delivery must not block |

### What to keep vs discard

| Keep (must) | Discard / avoid |
|-------------|-----------------|
| Main: live-status unique constraint + migration `0004_live_status_…` | UF’s `0004_dual_bucket…` **filename/number** as-is |
| Main: `_provider_ref_taken` live filter | Overwriting funding.py with pure UF version |
| Main: `maybe_resume_after_wallet_credit` + serializer field | Dropping `meal_service_restored` |
| Main: `audit_wallet_accounting` command | Committing `db.sqlite3` |
| UF: dual buckets, ledger strategies, commission types | Treating WIP commit as finished without retest on main |
| UF: referral app + hooks | Blind `git merge unfinished-features` into main without migration rewrite |

---

## Database Migration Analysis

| App | Main tip | UF tip | Issue |
|-----|----------|--------|-------|
| `wallet` | `…0004_live_status…` | `…0004_dual_bucket…` + `…0005_referral…` | **Duplicate 0004** — must resequence |
| `admin_wallet` | through `0004_inventory…` | + `0005_referral_commission_types` | OK if applied after main |
| `user_management` | through `0020_…` | + `0021_referral…` | OK |
| `referrals` | (absent) | `0001_referral…` | New app — OK |

Production impact of dual-bucket migrate: additive columns + copy; no destructive drop. Still requires maintenance window / backup and `verify_wallet_balance_consistency` before enabling `REFERRAL_ENABLED` accrual in prod.

---

## Decisions

### D1 — Recommended strategy: Option C hybrid on a new branch from `origin/main` (preferred over A/B alone)

**Decision:** Create `referral-integration` from updated `origin/main`, then **manually port / surgically merge** referral + dual-bucket changes, rewriting wallet migrations. Do **not** merge `unfinished-features` as a single black-box merge into production main without migration fix.

**Alternatives:**

| Option | Pros | Cons | Risk |
|--------|------|------|------|
| **A: merge UF into main** | Fast history | Immediate `0004` conflict; easy to drop hotfix wallet fixes | **HIGH** |
| **B: cherry-pick only** | One commit to pick | Still brings wrong migration filenames; conflict same as merge | **HIGH** |
| **C: new branch + selective port** | Explicit keep/discard; renumber migrations; easiest to review | More manual effort | **MEDIUM** (lowest practical) |

**Rationale:** Only one UF commit exists, but conflict density in wallet is high and migration graph is incompatible. Selective port forces conscious composition of main+UF wallet behavior.

### D2 — Migration sequencing on integration branch

1. Keep `wallet.0004_live_status_provider_recharge_ref_unique` from main.
2. Add dual-bucket as `wallet.0005_dual_bucket_balances` (depends on `0004_live_status…`).
3. Fold or renumber UF helptext migration as `0006_…` if still needed.
4. Keep `admin_wallet.0005_referral_commission_types`, `user_management.0021_…`, `referrals.0001_…`.

### D3 — Conflict resolution order when merging/porting

1. `wallet/migrations/*` (graph first)
2. `wallet/models.py`
3. `wallet/services/ledger.py` then `funding.py`
4. `wallet/api/serializers.py` (+ web views if touched)
5. `admin_wallet/*`
6. `user_management/*` (models → services → API)
7. `orders/services/order_delivery.py`
8. `core/settings/base.py`, `core/urls.py`
9. Docs / openspec / ignore `db.sqlite3`

### D4 — Feature flags for rollout

Ship code with ability to disable accrual (`REFERRAL_ENABLED=False`) until wallet verify + backfill succeed.

## Risks / Trade-offs

- [Wrong migration leaf applied on prod] → Rewrite graph before any deploy; never force UF `0004` onto DB that already has main `0004`.
- [Silent loss of hotfix funding behavior] → Checklist: provider-ref live filter + meal resume must appear in final `funding.py` / serializers.
- [Ledger/payment path miss] → Full wallet + delivery + referral test suite on integration branch.
- [Local main confusion] → Always base work on `origin/main` after fetch; update local `main`.
- [UF is local-only] → Push backup branch before rewrite so WIP is not lost.

## Migration Plan (integration execution — later apply phase)

1. `git fetch origin` && update local `main` to `origin/main`.
2. `git checkout -b referral-integration origin/main`.
3. Optional safety: `git branch backup/unfinished-features-135e5e7 unfinished-features`.
4. Port referral app + wallet dual-bucket + hooks; rewrite migrations per D2.
5. Manually reconcile conflict files per D3 — **keep both** wallet semantics.
6. `migrate` on disposable DB clone; run `verify_wallet_balance_consistency` + `audit_wallet_accounting`.
7. Run referral + wallet + funding + delivery tests.
8. Staging deploy with `REFERRAL_ENABLED=False`, then enable attribution, then accrual.
9. Rollback: disable flag; dual-bucket columns are forward-only — do not reverse in prod without a dedicated reverse plan.

### Suggested commands (operator)

```text
git fetch origin
git checkout main
git pull origin main
git checkout -b referral-integration

# Prefer selective port / merge with immediate migration rewrite.
# If merging for conflict discovery only:
#   git merge unfinished-features
# then fix wallet migrations BEFORE committing.

# Never:
#   git add db.sqlite3
```

## Open Questions

1. Should integration also re-apply unfinished OpenSpec change `referral-affiliate-commission-system` onto main specs, or keep it archived after port?
2. Is commission spend order (`commission_first` on meal payment) already accepted by finance for production?
3. Confirm production has already applied `wallet.0004_live_status_…` on EC2 (expected yes given hotfix merge).
