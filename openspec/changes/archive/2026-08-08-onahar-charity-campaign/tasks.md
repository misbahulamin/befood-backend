## 1. App scaffold and models

- [x] 1.1 Create `onahar` Django app, register in `INSTALLED_APPS`, and add `ONAHAR_ENABLED` (or equivalent) settings flag defaulting to enabled
- [x] 1.2 Implement models: settings/target history, customer monthly progress (with target snapshot), point events, contributions, fund ledger entries, distributions, distribution media, privacy preference, audit log — all public API resources with `PublicIdMixin` where exposed
- [x] 1.3 Add DB constraints/indexes (unique delivery credit/reverse events, unique customer+month progress, ledger ordering) and run migrations
- [x] 1.4 Seed default `OnaharSettings` with contribution target `50`; register models in Django admin for ops inspection

## 2. Contribution engine services

- [x] 2.1 Implement `credit_for_delivery(delivery)` with atomic idempotent +1 point, monthly cycle open/snapshot, and immediate contribution + fund credit when multiples of target are crossed
- [x] 2.2 Implement `reverse_for_delivery(delivery)` with atomic −1 reverse event, contribution/fund compensating adjustments, and audit entries
- [x] 2.3 Implement month-close service + management command `close_onahar_month` (idempotent expiry of remainders, cycle `closed`, audit)
- [x] 2.4 Implement verified-admin target update service that writes history and does not rewrite closed (or already-snapshotted) cycles by default
- [x] 2.5 Hook credit/reverse into order delivery mark-delivered and refund/undo service paths; gate with `ONAHAR_ENABLED`

## 3. Fund and distribution services

- [x] 3.1 Implement fund ledger helpers (credit/debit, available balance from ledger, optional denormalized cache in same transaction)
- [x] 3.2 Implement distribution create/update-draft, media attach with file validation, publish (balance check + debit), and cancel (restore credit) services
- [x] 3.3 Enforce immutable meal count after publish; write audit logs for create/edit/publish/cancel/media/fund movements

## 4. Public transparency APIs

- [x] 4.1 Mount public routes under `onahar/` and implement `GET /onahar/stats/` from live aggregates
- [x] 4.2 Implement paginated `GET /onahar/leaderboard/` with privacy-safe display names (`public` | `partial` | `anonymous`) and no PII fields
- [x] 4.3 Implement paginated `GET /onahar/ledger/` for contribution and distribution transparency entries
- [x] 4.4 Implement `GET /onahar/distributions/` and `GET /onahar/distributions/{public_id}/` for published campaigns + media (hide drafts)

## 5. Customer dashboard APIs

- [x] 5.1 Implement authenticated `GET /onahar/me/` (current progress, lifetime totals, ranking) scoped to caller only
- [x] 5.2 Implement authenticated paginated `GET /onahar/me/history/` with month/target/points/contribution/expiry fields
- [x] 5.3 Implement `GET|PATCH /onahar/me/privacy/` for allowlisted privacy preference values

## 6. Admin management APIs

- [x] 6.1 Mount `api/v1/web/onahar/` and implement `GET|PATCH` settings + target history with `IsVerifiedAdmin`
- [x] 6.2 Implement admin distribution list/detail/create/update/media/publish/cancel endpoints with fund rules
- [x] 6.3 Implement admin fund summary and audit log list endpoints (filters/pagination allowlisted)

## 7. OpenAPI, tests, and docs

- [x] 7.1 Add OpenAPI helpers/examples for public, customer, and admin Onahar endpoints
- [x] 7.2 Write tests for point idempotency, monthly math/multi-contribution, no carry-forward, target snapshot stability, refund adjustments, fund over-debit rejection, publish/cancel restore, privacy masking, authz (401/403), and month-close idempotency
- [x] 7.3 Write `onahar/docs/backend/` technical documentation (models, workflows, hooks, jobs, errors)
- [x] 7.4 Write `onahar/docs/frontend/` implementation guide covering public page, customer dashboard, homepage teaser, admin UI, all endpoints with request/response examples, auth, errors, pagination, media, and monthly calculation behavior
- [x] 7.5 Add optional reconcile command (delivered without point event) and document cron schedule for `close_onahar_month`
