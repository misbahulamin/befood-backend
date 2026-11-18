# Design

## Context

See proposal.md for motivation. Current behavior lives in `delivery_zones/services/unassigned_digest.py`:

- `notify_admins_unassigned_delivery_digest` always composes and sends mail when recipients exist, including `rows=[]` with subject `[BeFood] Unassigned delivery subscribers (0) — none pending`.
- `run_unassigned_delivery_digest` and `send_unassigned_delivery_digest` treat empty send as success (`email_sent=True`).
- Tests and `delivery_zones/docs/backend/unassigned-delivery-digest.md` assert that empty-run summary email.

Query membership, cron schedule, recipients, and non-empty email format are unchanged.

## Goals / Non-Goals

**Goals:**

- Early-return in the notify path when `len(rows) == 0` so no SMTP send occurs.
- Keep `UnassignedDigestRunResult` truthful: empty → `candidate_count=0`, `email_sent=False`, `errors=0` (unless a real failure).
- Align tests and backend docs with skip-on-empty.
- Preserve dry-run (still no send) and non-empty digest content/subject.

**Non-Goals:**

- Changing candidate query, slots, cron installer, or recipient resolution.
- Adding a new “heartbeat” channel (Slack, push, etc.) to replace empty emails.
- Changing non-empty subject/body columns or branding.

## Decisions

### 1. Skip inside `notify_admins_unassigned_delivery_digest`

- **Choice:** After dry-run and recipient checks (or before recipient resolution when `rows` is empty), return `False` immediately when `not rows`, with an info log (`candidate_count=0`, skipped empty digest).
- **Why:** Single send gate; command/run helper already set `email_sent` from the return value. Avoids composing empty HTML/plain bodies that nothing will send.
- **Alternatives considered:** Skip only in `run_unassigned_delivery_digest` and leave notify callable for empty sends — rejected; notify is also tested/used directly and must match product rule. Keep empty send with a quieter subject — rejected by product (no mail at all).

### 2. Prefer skip before recipient lookup on empty

- **Choice:** When `rows` is empty and not dry-run, skip without calling `resolve_funding_admin_emails()`.
- **Why:** No work / no “no recipients” warning for a run that was never going to notify. Dry-run may still log `candidate_count=0`.
- **Alternatives considered:** Resolve recipients then skip — harmless but noisier logs.

### 3. Remove empty-body format paths only if unused

- **Choice:** Leave `_format_admin_plain` / `_format_admin_html` empty branches in place for now, or delete them if nothing calls them after the early return; prefer delete-or-dead-code cleanup only if tests no longer need them.
- **Why:** Behavior change is the send gate; formatter cleanup is optional hygiene, not required for the requirement.
- **Alternatives considered:** Force-keep empty formatters for future use — unnecessary.

### 4. Ops visibility via logs only

- **Choice:** Document that empty runs are confirmed in `logs/cron-unassigned-delivery-digest.log` / structured `as_log_dict()` (`candidate_count=0`, `email_sent=false`), not inbox.
- **Why:** Matches REMOVED requirement migration; no new monitoring dependency in this change.
- **Alternatives considered:** Emit a metrics counter — out of scope.

## Risks / Trade-offs

- [Ops may think cron is broken when no mail arrives] → Document in backend digest doc; ensure cron still logs every run with `candidate_count` and exit 0.
- [Someone still calling notify with `rows=[]` expecting True] → Return False; update unit tests that asserted empty send.
- [Prior change design explicitly chose empty heartbeats] → This change deliberately reverses that product decision; prior completed change artifacts stay historical.

## Migration Plan

1. Change notify early-return + update docstrings.
2. Flip empty-run tests (`test_empty_run_sends_summary`, `test_command_empty_path_sends_summary`) to assert no mail / `email_sent=False`.
3. Update `unassigned-delivery-digest.md` empty-list and subject examples.
4. Deploy; no cron installer change. Rollback = restore previous notify empty-send behavior if ops insist on heartbeats.
