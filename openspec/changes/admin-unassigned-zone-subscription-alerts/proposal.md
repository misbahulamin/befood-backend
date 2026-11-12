# Proposal

## Why

Customers can activate a meal subscription before an admin assigns an operational delivery sub-location. Those subscribers never appear on rider boards and are easy to miss until a delivery fails. Ops needs a reliable twice-daily reminder so admins can assign zone hierarchy before meals are prepared.

## What Changes

- Add a backend digest that finds customers with an **active** meal subscription and **no** `delivery_sub_location` assignment.
- Email verified admin recipients twice daily at **18:00 and 22:00 Asia/Dhaka** (managed cron in UTC) with each customer's name, phone, subscription time, and email when available.
- Add a Django management command, cron wrapper script, and managed-cron installer entries so production sends the digest automatically after deploy (no deploy YAML change).
- Support `--dry-run` for safe operator verification without sending mail.
- When the candidate list is empty, still send a short “no unassigned subscribers” summary so ops can confirm the job ran.

## Capabilities

### New Capabilities

- `admin-unassigned-delivery-digest`: Query and email verified admins a structured report of active subscribers missing operational delivery sub-location assignment, including required contact columns and empty-run behavior.
- `unassigned-delivery-digest-cron`: Management command, wrapper script, logging/locking, and Asia/Dhaka schedule wiring for the unassigned-delivery digest.

### Modified Capabilities

- `managed-cron-install`: Register the new digest wrapper jobs in the managed crontab block without removing existing auto-delivery or wallet-threshold jobs, still without deploy YAML edits.
- `managed-cron-runtime`: Extend the documented UTC schedule set with 18:00 and 22:00 Asia/Dhaka digest entries while preserving absolute venv Python, flock, and logging rules for the new wrapper.

## Impact

- `delivery_zones` (or shared notifications service): new digest query + email composition service; new management command package if missing.
- `scripts/cron/`: new `run_unassigned_delivery_digest.sh` wrapper; updates to `install_managed_cron.sh`.
- Reuses `resolve_funding_admin_emails()` recipient resolution and existing SMTP settings (`EMAIL_*`, `DEFAULT_FROM_EMAIL`).
- Reuses assignment semantics from `CustomerProfile.delivery_sub_location` and active-subscription filter (`CustomerSubscription.status=active`).
- Spec deltas for `managed-cron-install` and `managed-cron-runtime` schedule inventories.
- Tests for query membership, email payload fields, dry-run, empty list, and installer schedule presence.
- No customer-facing API or frontend contract changes in this change.
