# Tasks

## 1. Skip empty digest send

- [x] 1.1 In `notify_admins_unassigned_delivery_digest`, early-return `False` when `rows` is empty (prefer before recipient resolution; log skip with `candidate_count=0`) and update the docstring so it no longer says empty runs still send — verify by reading the function: empty path returns without calling `EmailMultiAlternatives.send`
- [x] 1.2 Optionally remove unused empty branches in `_format_admin_plain` / `_format_admin_html` if nothing else needs them after 1.1 — verify no remaining callers rely on empty-body formatting (grep / tests still pass)
- [x] 1.3 Update `delivery_zones/tests/test_unassigned_digest.py`: change `test_empty_run_sends_summary` and `test_command_empty_path_sends_summary` to assert no mail (`len(mail.outbox)==0`), `sent`/`email_sent` is False, and keep a non-empty send regression assertion — verify with `python manage.py test delivery_zones.tests.test_unassigned_digest`
- [x] 1.4 Update `delivery_zones/docs/backend/unassigned-delivery-digest.md` so empty candidate lists do not send mail, drop the `(0) — none pending` subject example, and note ops should use cron logs for empty-run confirmation — verify the doc matches the new behavior described in the spec delta

## Workflow follow-up

- Archive the change after review when ready (`/opsx-archive` or project archive flow).
- Consider syncing `admin-unassigned-delivery-digest` into `openspec/specs/` if that capability was never promoted from `admin-unassigned-zone-subscription-alerts`.
