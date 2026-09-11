## Context

BeFood supports multiple customer registration methods. Phone OTP registration creates a `User` with blank `email` (`''`), `CustomerProfile.is_phone_verified=True`, and `is_email_verified=False`. Subscribe is already gated by `is_customer_identity_verified` (phone **or** email **or** social)—not by email string presence.

Initial production hypothesis (“slot creation requires email”) is **not supported** by the creation path: `ensure_subscription_deliveries` never checks email. Zero slots after an `ACTIVE` subscription most often come from the **published monthly menu gate** (skip dates when `published_schedule_for_meal` is missing). Separately, leftover `is_email_verified=True` filters in wallet-threshold and meal-close low-balance queries exclude phone-only users from **ops automation**, which can look like “service never started.”

Stakeholders: customers on phone-only accounts, support/admin, kitchen/ops cron, mobile app (likely no mandatory change).

Constraints: no destructive production data migration; no email backfill; no subscription reset; no OrderDelivery rewrite; prefer future-flow fixes + read-only audit + safe re-run of existing ensure when menus are published.

## Goals / Non-Goals

**Goals:**

- Codify phone-or-email identity as valid for subscribe and delivery-slot generation.
- Guarantee that identity-verified phone-only subscribers get OrderDelivery rows when published menus cover the rolling horizon.
- Remove residual email-only filters from wallet-threshold / meal-close candidate queries (use identity-verified parity).
- Ship a read-only production audit for active subscriptions missing slots (diagnose menu vs other).
- Clarify mobile/admin impact; update stale docs that claim email verification is required for subscribe.
- Add regression tests for phone-only subscribe → slots (with published menu) and no duplicate slots when email is added later.

**Non-Goals:**

- Forcing email capture on phone registration or subscription.
- Inventing/backfilling emails for existing users.
- Changing Google/Facebook OAuth (currently hidden).
- Rewriting historical OrderDelivery / subscription rows.
- Making address mandatory in a way that blocks subscribe if product already allows address snapshot later (address gaps are documented separately; optional mobile warning only).
- Building a full admin “registration method” UI in this change (optional follow-up; docs/notes only unless trivial API field already exists).

## Decisions

### D1 — Treat audit findings as the implementation north star

**Choice:** Fix confirmed residual email filters and harden/tests around identity + published-menu behavior; do **not** invent a new “remove `if user.email`” gate that does not exist in slot creation.

**Alternatives:** Blindly rewrite subscribe to “check CustomerProfile only” without diagnosing menu gate → would miss root cause of empty slots.

**Rationale:** Honest RCA prevents wrong fixes and wasted mobile changes.

### D2 — Identity source of truth remains `is_customer_identity_verified`

**Choice:** Keep / reuse `user_management/services/identity_verification.py` for subscribe permissions and for ops querysets (replace `is_email_verified=True`).

**Alternatives:** New “has_email_or_phone” field; backfill `is_email_verified` for phone users (semantically wrong).

**Rationale:** Already used by `SubscribeSerializer` / `IsVerifiedCustomer`; phone-only path is intentional.

### D3 — Slot creation remains menu-gated; improve observability

**Choice:** Keep `ensure_subscription_deliveries` published-menu skip behavior (correct product rule). Add clearer logging/metrics or audit report columns so ops can see “active sub, 0 slots, unpublished menu” vs “identity filter.”

**Alternatives:** Create placeholder slots without published menu → breaks kitchen/pricing assumptions.

**Rationale:** Empty slots with unpublished menus are expected; mis-attribution to email must stop.

### D4 — Ops parity filter rewrite

**Choice:** In `candidate_customers_queryset` (`wallet_balance_thresholds.py`) and `slot_low_balance_deliveries` (`meal_close.py`), replace `is_email_verified=True` with the same identity rule (Q phone verified | email verified | social), or filter via a shared helper queryset.

**Alternatives:** Leave filters and only fix docs → phone-only still invisible to meal-stop/resume/low-balance crons.

**Rationale:** Matches business rule that phone-only customers are valid.

### D5 — Production data safety

**Choice:** Read-only management command or documented SQL report for affected users; remediation for missing slots = ensure menus published + re-run existing `ensure_subscription_deliveries` (idempotent), not data migration.

**Alternatives:** Auto-backfill emails; force status flips.

**Rationale:** User constraint: no destructive migration.

### D6 — Mobile / admin

**Choice:** Backend-first. Mobile change only if registration/subscribe contracts are broken (audit suggests they are not). Optional: client warning when delivery address incomplete—never require email. Admin: blank email remains valid; registration-method badge optional later.

## Risks / Trade-offs

- **[Risk] Symptom misdiagnosed as email gate while menus unpublished** → Mitigation: Phase-1 audit report splits “missing slots + unpublished menu” vs “missing slots + published menu” (true bug).
- **[Risk] Broadening identity filters increases cron volume** → Mitigation: same ACTIVE subscription scope already intended; monitor job duration.
- **[Risk] Support still forces email on customers** → Mitigation: update backend/frontend docs; optional admin registration-method display later.
- **[Risk] Address missing causes incomplete snapshots** → Mitigation: document separately; do not conflate with email; optional mobile address CTA.
- **[Trade-off] No automatic healing of historical empty subs beyond ensure re-run** → Acceptable under no-rewrite constraint; ops run ensure after publish.

## Migration Plan

1. **Deploy code:** identity filter parity + tests + docs (no schema change expected).
2. **Read-only audit** on production (or replica): count active subs with zero OrderDelivery; join published schedule status; phone-only vs email cohorts.
3. **Ops remediation:** publish missing menus for packages; run `ensure_subscription_deliveries` (or ensure-all); verify slot counts for sample phone-only users.
4. **Rollback:** revert filter/doc/test commits; no data migration to undo.
5. **Mobile/admin:** ship only if audit proves API gap; otherwise docs-only.

## Open Questions

1. For active subscriptions with published menus but still zero slots—is there a second failure mode (exception swallowed, wrong meal_id, horizon edge)? Confirm during apply Phase 1 with concrete production IDs.
2. Should subscribe API surface a structured warning when zero slots were created due to unpublished menu (client UX), or remain silent as today?
3. Is delivery address required before first service day, or only at delivery time? Align mobile warning with existing `resolve_and_apply_snapshot` rules.
4. Priority of optional admin `registration_method` field vs filter fixes only.
