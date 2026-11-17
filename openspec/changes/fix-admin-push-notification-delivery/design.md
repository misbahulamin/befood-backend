# Design

## Context

See `proposal.md` for motivation. Observed production symptoms match the current dispatch split:

1. `create_campaign` marks users with no active `DeviceToken` as recipient `failed` (`No active device`) and increments `total_failed` immediately.
2. `dispatch_push_campaign` creates customer inbox rows for all non-skipped targets **before** FCM send (introduced in `b5f465b`), so Flutter web inbox at `app.befood.com.bd` can show the message while admin `sent` stays `0`.
3. FCM send (`send_to_tokens`) now attaches `WebpushConfig` on every multicast batch. There is no outer try/except around unexpected Firebase/SDK exceptions after inbox creation, so a raised error leaves `PushCampaign.status=processing` with only pre-create failures reflected in counters.
4. Async dispatch still uses an in-process daemon thread (`enqueue_dispatch`). Worker recycle can strand campaigns; `dispatch_push_campaign --stuck-only` exists but needs the dispatch function itself to be exception-safe and idempotent for pending recipients.

Relevant code: `notifications/services/notification_sender.py`, `fcm_service.py`, `device_service.py`, admin send view, `user_management.DeviceToken` (+ migration `0025_device_token_length_512`).

## Goals / Non-Goals

**Goals:**

- Restore reliable Android (and iOS) FCM delivery for admin campaigns.
- Keep Flutter web inbox behavior, and allow web FCM when a valid `platform=web` token exists.
- Guarantee campaigns exit `processing` after a dispatch attempt.
- Keep admin `total_sent` = FCM successes only; document/test the inbox vs push distinction.
- Make platform-mixed campaigns safe (native success independent of web token failures).

**Non-Goals:**

- Migrating async dispatch to Celery/RQ in this change (keep thread + management command; optionally note future worker).
- Redesigning the admin React UI beyond what current API fields already expose.
- Changing customer inbox list/read API contracts unless a bug blocks verification.
- Rebuilding Flutter client; client verification is out-of-repo except documenting required token registration/platform.

## Decisions

### 1. Platform-split FCM message construction

**Decision:** Split tokens by `DeviceToken.platform` before send. Native (`android`/`ios`) batches use `AndroidConfig` (channel/priority) without relying on web-only options for correctness. Web batches use `WebpushConfig` (click link) plus notification/data payload.

**Why:** Commit `b5f465b` added `WebpushConfig` to every multicast. Platform-split isolates web push failures and clarifies payloads. Per-token FCM responses already exist; splitting reduces cross-platform blast radius.

**Alternatives considered:** Keep one multicast with both configs (simpler, current) — rejected as primary approach because production shows stuck/zero-sent after that change; keep as fallback only if split proves unnecessary after tests.

### 2. Hardened dispatch lifecycle

**Decision:** Wrap FCM send + recipient updates in try/except/finally-style control flow so that:

- Unexpected exceptions mark remaining `pending` recipients `failed` with a safe message.
- Campaign status becomes `failed` if no FCM successes and the failure is campaign-level/unrecoverable; otherwise `completed` with accurate counters (aligned with existing partial-failure model).
- Inbox creation stays best-effort and still runs for non-skipped targets, but must not leave FCM unattempted when tokens exist.
- Re-dispatch of stuck campaigns only processes remaining `pending` recipients (already true) and does not duplicate inbox rows for users who already have a campaign-linked inbox entry (dedupe by campaign content object / user).

**Why:** Matches the stuck `processing` + inbox-visible symptom exactly.

**Alternatives considered:** Only document `--stuck-only` without code harden — insufficient. Move to Celery now — higher scope.

### 3. Narrow invalid-token deactivation

**Decision:** Keep auto-deactivate only for clearly unregistered/invalid token errors. Review `_classify_error` so overly broad markers (e.g. generic `invalid-argument` from payload/config mistakes) do not mass-deactivate healthy Android tokens.

**Why:** Aggressive deactivation would permanently drop `sent` to zero for many users after one bad web/config error.

### 4. Token length 512 is required in prod

**Decision:** Treat migration `0025_device_token_length_512` + serializer/service max 512 as required for web tokens. Specs catch up to code. Verify migration applied on production during rollout.

### 5. Metrics semantics (no new counter field in MVP)

**Decision:** Do not add `total_inbox_created` in this change unless implementation proves operators cannot interpret list UI. Document that inbox ≠ sent. Detail endpoint already exposes recipient `error_message` for “No active device” vs FCM errors.

**Alternatives considered:** New admin fields — deferred to avoid admin frontend coupling in the same fix.

## Risks / Trade-offs

- **[Risk] Production Firebase web push (VAPID / Web credentials) misconfigured** → Mitigation: native batches still succeed; web failures recorded per recipient; ops checklist in docs.
- **[Risk] Daemon thread still dies mid-send** → Mitigation: exception-safe finalize + cron/operator `--stuck-only`; consider non-daemon or management-command-first dispatch later.
- **[Risk] Inbox dedupe on re-dispatch** → Mitigation: skip creating a second `Notification` when one already exists for the same user + campaign GFK.
- **[Risk] Many users truly have no active Android token after web rollout** → Mitigation: recipient errors make this visible; clients must re-register `platform=android` tokens; not a backend silent drop.
- **[Trade-off] Platform-split increases FCM API calls** → Acceptable vs broken mixed batches; still chunked at 500.

## Migration Plan

1. Deploy backend with hardened dispatch + platform-aware FCM.
2. Confirm `0025_device_token_length_512` applied.
3. Run `manage.py dispatch_push_campaign --stuck-only` to clear stranded campaigns.
4. Send a single-user test to a known Android device and a known web session; confirm admin counters and both clients.
5. Rollback: revert deploy; stuck campaigns can still be inspected; no destructive data migration beyond token length (already additive).

## Open Questions

- Whether production Firebase project has web push certificates configured (ops verify; does not change backend task list).
- Whether Flutter web currently registers FCM tokens after notification permission (client verify during apply).
