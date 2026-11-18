# Proposal

## Why

Twice-daily unassigned-delivery digest emails currently go to admins even when there are zero unassigned subscribers (`[BeFood] Unassigned delivery subscribers (0) — none pending`). That empty “heartbeat” is inbox noise and no longer useful; admins only need the mail when there is real assignment work.

## What Changes

- **Skip empty digests**: When a non-dry-run digest finds zero unassigned active subscribers, do **not** send email to admins.
- Keep sending the structured digest (name, phone, subscription time, email) whenever `candidate_count >= 1`.
- Empty runs remain successful: query/log/command exit normally with `email_sent=false` and `candidate_count=0` (no failure, no empty “none pending” subject).
- Update tests and backend docs that currently assert empty-run emails are sent.
- **BREAKING** (ops expectation): Empty runs will no longer produce a confirmation email; cron/job health should be inferred from logs (`candidate_count`, exit status), not from inbox heartbeats.

## Capabilities

### New Capabilities

<!-- None — behavior change on an existing digest capability. -->

### Modified Capabilities

- `admin-unassigned-delivery-digest`: Replace the “empty digest still confirms the run” requirement with skip-send when there are no unassigned subscribers. (Capability shipped via `admin-unassigned-zone-subscription-alerts`; not yet under `openspec/specs/`, but same path is reused.)

## Impact

- `delivery_zones/services/unassigned_digest.py` — `notify_admins_unassigned_delivery_digest` (and callers’ expectations)
- `delivery_zones/tests/test_unassigned_digest.py` — empty-run / command empty-path cases
- `delivery_zones/docs/backend/unassigned-delivery-digest.md` — empty-list email wording
- Cron schedule and recipient resolution stay unchanged; non-empty digests and dry-run behavior stay unchanged
