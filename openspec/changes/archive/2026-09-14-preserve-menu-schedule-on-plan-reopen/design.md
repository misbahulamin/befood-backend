## Context

BeFood is live in production. Meal cycle workflow: admin builds a servings matrix → finalize plan → create `MonthlyMenuSchedule` → assign day-wise lunch/dinner ingredients → optionally publish schedule. Admins sometimes reopen a finalized plan to tweak servings or profit margin.

Current implementation in `reopen_plan()` (`meals/services/cycle_calculations.py`):

```python
schedule = MonthlyMenuSchedule.objects.filter(plan_id=plan.pk).first()
if schedule is not None:
    if schedule.is_published:
        raise ValidationError(...)  # keep
    # Draft schedule would become quota-orphan after line edits — delete it.
    schedule.delete()
```

`MonthlyMenuSchedule` is a `OneToOneField` to `MealCyclePlan` with `on_delete=CASCADE` (only when the **plan row** is deleted, not on reopen). Slot items reference `Ingredient` directly; they do not FK to `MealCyclePlanLine`. Therefore preserving the schedule on reopen is a **single-service deletion removal**, not a schema change.

`replace_plan_lines()` deletes and recreates plan lines only — it never touches `MonthlyMenuSchedule`. The admin-perceived "servings change deletes schedule" path is: finalize → schedule → reopen (deletes schedule) → edit servings.

OpenSpec currently allows delete-on-reopen (`meal-cycle-planning` requirement). This change aligns spec with desired product behavior.

## Goals / Non-Goals

**Goals:**

- Reopen finalized plan → plan becomes `draft`, cost snapshots cleared, **draft menu schedule and all slot assignments preserved**.
- Servings matrix save (`PUT .../lines`) → recalculated summary/costs only; schedule unchanged.
- Re-finalize after reopen → schedule still linked; no duplicate schedule created.
- Published schedule guard on reopen unchanged (must unpublish first).
- Quota enforcement on assignment save/publish catches over-assignment after servings shrink.
- Frontend copy reflects non-destructive reopen.
- Regression tests cover reopen + servings + re-finalize paths.

**Non-Goals:**

- Database migration or new models.
- Allowing schedule **create** on draft plans (create still requires finalized plan — existing schedule may remain while plan is draft after reopen).
- Auto-trimming schedule assignments when servings decrease (admin fixes via calendar or publish validation).
- Changing published-schedule immutability or slot price snapshot rules.
- Cross-package schedule isolation changes (already covered by `monthly-menu-package-isolation` spec).

## Decisions

### 1. Remove `schedule.delete()` on reopen (minimal fix)

**Choice:** Delete lines 419–420 in `reopen_plan()` only.

**Alternatives considered:**

| Alternative | Why rejected |
| --- | --- |
| Clear assignments but keep schedule shell | Still destructive; user wants full preserve |
| Block reopen until admin deletes schedule | Worse UX; current frontend already warns destructively |
| Soft-delete / archive schedule | Requires migration and new status; over-scoped |

**Rationale:** Smallest diff; zero migration; FK model already supports draft plan + existing schedule row.

### 2. Rely on existing quota validation instead of pre-emptive schedule wipe

When servings shrink below current assignment totals, `replace_schedule_assignments` and `publish_schedule` already reject over-quota via `build_quota_summary()`. Admin can adjust the calendar manually. No automatic deletion.

**When ingredient removed from plan:** Existing assignments may reference an ingredient no longer on the plan. `_validate_assignment_matrix` rejects **new** saves that include off-plan ingredients; **existing** slot items remain readable until admin edits. Publish runs quota check — off-plan ingredients may still appear in slots. Optional follow-up: warn in admin UI if schedule references removed ingredients (out of scope unless needed in testing).

### 3. No change to finalize or replace_plan_lines

`finalize_plan()` does not touch schedules. `replace_plan_lines()` already preserves schedules. No additional hooks.

### 4. Frontend: copy-only change

Update `AdminCyclePlanEditorPage.tsx`:

- Confirm dialog: remove "will delete draft menu schedule"
- Inline hint below schedule link: remove "reopening will delete the draft schedule"
- Keep published-schedule unpublish toast before reopen

No cache-clear or schedule state reset logic exists in `useReopenAdminCyclePlan` beyond standard query invalidation (correct — refetch preserved schedule).

### 5. Test strategy

| Test | Assertion |
| --- | --- |
| `test_reopen_preserves_draft_schedule` (rename from delete test) | Schedule exists; assignments unchanged after reopen |
| New: reopen → replace lines (servings change) → schedule + assignments intact | |
| New: reopen → finalize again → single schedule, no duplicate | |
| Existing: `test_reopen_blocked_when_schedule_published` | Unchanged |
| Sibling package isolation tests | Unchanged |

## Risks / Trade-offs

- **[Risk] Schedule exceeds quotas after servings decrease** → Mitigation: publish and assignment PUT still validate quotas; admin sees over-quota in quota summary UI.
- **[Risk] Schedule references ingredient removed from plan** → Mitigation: new assignment saves reject off-plan ingredients; document that admin should fix calendar before publish; optional admin warning later.
- **[Risk] Draft plan + existing schedule confuses "create schedule" button** → Mitigation: frontend already checks `linkedSchedule` before create; schedule remains in list query by `plan_id`.
- **[Risk] Behavioral change for admins who relied on implicit cleanup** → Mitigation: explicit schedule delete endpoint remains; update docs and confirm copy.

## Migration Plan

1. Deploy backend (remove delete) — safe for existing data; no backfill.
2. Deploy frontend copy update.
3. No rollback migration needed; rollback re-enables delete behavior (undesirable but safe).

## Open Questions

- _(none blocking)_ — Product confirmed: preserve schedule on reopen and servings edit.
