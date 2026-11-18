# Design

## Context

See `proposal.md` for motivation. Observed bug: `orders/services/wallet_balance_thresholds.candidate_customers_queryset` selects

`Q(active subscription) | Q(meal_service_blocked_low_balance=True)`.

Cancelled (or never-subscribed) customers who still have the block flag are evaluated, get meal-stop/reminder notifications, and land in `notify_admins_low_balance_summary` with Package `N/A` from `active_package_name`. `cancel_subscription` does not clear the block flag today.

Specs already intended “active meal subscription” for reminders and cron evaluation; the blocked-flag OR widened the cohort beyond that.

## Goals / Non-Goals

**Goals:**

- Single eligibility rule for cron remind / meal-stop notify / admin affected rows: verified + active user + **active** `CustomerSubscription`.
- Clear leftover blocks on cancel so cancelled users are not “low balance” for reporting or cron notify.
- Tests and backend docs that prove Package `N/A`/cancelled rows no longer appear in the admin report.

**Non-Goals:**

- Changing kitchen / meal-close low-balance lists (delivery-scoped; separate from this digest).
- Changing threshold values, email templates layout, cron schedule, or post-debit meal-stop for still-active subscribers.
- Backfilling historical admin emails already sent.

## Decisions

1. **Tighten candidate queryset to active subscribers only**  
   Drop the `meal_service_blocked_low_balance=True` OR from the cron candidate set. Reminder, meal-stop apply/notify, and admin `affected` rows all flow from that queryset, so one gate fixes report + customer notifications together.  
   *Alternative considered:* Keep blocked-non-subscribers in the loop for silent resume only — rejected because it keeps cancelled users in the evaluated set and risks accidental notify/report inclusion; cancel-time clear covers hygiene better.

2. **Clear block on subscription cancel**  
   In `cancel_subscription` (after successful cancel transition), clear `meal_service_blocked_low_balance` / `meal_service_blocked_at` when set. Idempotent for already-cancelled returns.  
   *Alternative considered:* One-off data migration only — rejected; without cancel-path clear the bug returns on every future cancel.

3. **Credit-path resume stays available**  
   `maybe_resume_after_wallet_credit` / `resume_meal_service_after_balance_recovery` may still clear a stale block if one somehow remains (safe no-op if already cleared). No admin summary or customer low-balance notify from that path.

4. **Active subscription definition**  
   Same as existing helpers: `CustomerSubscription.Status.ACTIVE`. Package label continues via `active_package_name` (must resolve for every report row after the filter).

5. **Post-debit meal-stop**  
   Leave `evaluate_meal_stop_after_debit` as-is for this change unless tests prove non-subscribers can be charged without an active subscription; meal charges are tied to live deliveries. If a gap appears during apply, gate with the same active-subscription check—do not expand scope preemptively.

## Risks / Trade-offs

- **[Risk] Orphan blocked flags remain for customers cancelled before this fix** → Mitigation: optional one-liner cleanup in apply (clear block where no ACTIVE subscription) inside the same change’s tasks; cancel path prevents new orphans.
- **[Risk] Blocked active subscriber who cancels mid-day loses block flag before cancel skips finish** → Mitigation: cancel already soft-skips scheduled deliveries; clearing the block does not re-activate cancelled subscription meals.
- **[Trade-off] Cron no longer “resumes” cancelled blocked users** → Acceptable; they should not stay in the low-balance cohort. Credit resume still clears a leftover flag if needed.

## Migration Plan

1. Deploy code: queryset tighten + cancel clear + tests.
2. Optional: one management/data cleanup for existing `meal_service_blocked_low_balance=True` without ACTIVE subscription (can be inline in first cron run or a small admin script—prefer explicit clear in apply tasks).
3. Rollback: revert the change; stale flags may reappear for cancelled users until re-fixed.

## Open Questions

None blocking planning. Residual orphans before deploy are handled as an apply-time cleanup task.
