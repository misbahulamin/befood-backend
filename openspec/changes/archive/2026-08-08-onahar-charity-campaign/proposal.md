## Why

BeFood wants a transparent, emotionally engaging charity campaign (“অনাহার”) so every eligible customer meal can fund meals for people in need—without opaque manual counting. Today there is no contribution engine, public impact ledger, or admin distribution workflow, so marketing claims cannot be proven and customers cannot see how their orders create social impact.

## What Changes

- Add a dedicated **Onahar** domain (new Django app) for contribution targets, monthly customer progress, contribution records, fund ledger, distribution campaigns, media proofs, privacy preferences, and audit logs.
- Credit **1 Onahar Point per eligible delivered meal**; convert points to **Onahar Meal contributions** using an admin-configurable monthly target (default **50 meals = 1 contribution**), with per-cycle target snapshots so history stays stable when the target changes.
- Enforce **calendar-month cycles**: incomplete points do not carry forward; multiple contributions per month are allowed when points are multiples of the target; remaining points expire at month end via an idempotent automation job.
- Maintain a **meal-unit Onahar Fund** via append-only ledger (credits from contributions, debits from published distributions); available fund = total credited − total debited; reject distributions that exceed available balance (no override in v1 unless later authorized).
- Expose **public (unauthenticated) transparency APIs**: overall stats, contributor leaderboard (privacy-aware display names), contribution/distribution ledger views, and distribution history/detail with media.
- Expose **authenticated customer APIs**: current-month progress, lifetime totals, contribution history, ranking, and display-name privacy preference (`public` | `partial` | `anonymous`).
- Expose **verified-admin APIs**: change contribution target (with change history), create/edit/publish/cancel distributions with meal counts and proof media, and inspect fund/audit state.
- Hook contribution processing into **delivered meal** completion (and refund/reversal adjustments) with per-delivery idempotency so points never double-count.
- Add backend + frontend documentation so web/mobile clients can implement Public Onahar Page, Customer Dashboard, Homepage teaser stats, and Admin Onahar management without reading backend source.
- No **BREAKING** changes to existing order, wallet, or customer profile contracts; this change is additive.

## Capabilities

### New Capabilities

- `onahar-contribution-engine`: Monthly Onahar points from eligible delivered meals, admin-configurable target with cycle snapshots, multi-contribution math, month-end expiry automation, refund/adjustment audit trail, duplicate prevention.
- `onahar-fund-and-distribution`: Meal-unit fund ledger, distribution campaigns with location/date/counts/media, publish-time fund debit, cancel/restore rules, available-balance enforcement.
- `onahar-public-transparency`: Unauthenticated public stats, leaderboard, transparency ledger, and distribution gallery/detail with privacy-safe contributor display names.
- `onahar-customer-dashboard`: Authenticated customer progress, lifetime/history, ranking, and privacy preference for public display.
- `onahar-admin-management`: Verified-admin target configuration, distribution management, and audit/fund inspection APIs.
- `onahar-frontend-docs`: Frontend implementation documentation for public page, customer dashboard, homepage teaser, and admin panels (endpoints, examples, auth, errors, UX flows).

### Modified Capabilities

- (none) — existing order-delivery and customer contracts remain authoritative; Onahar consumes delivered/refunded meal signals without changing their public requirements.

## Impact

- **New app:** `onahar/` (models, services, APIs, admin, management command/job, tests, docs).
- **Integration:** `orders` delivery completion / refund paths call Onahar services (signals or explicit service hooks); no monetary wallet coupling.
- **URLs:** Public + customer under a domain prefix (e.g. `/onahar/`); admin under `/api/v1/web/onahar/` (or equivalent web mount), gated by `IsVerifiedAdmin`.
- **Data:** New tables for settings/target history, monthly progress, point events, contributions, fund ledger, distributions, media, privacy prefs, audit logs; all public resources use `PublicIdMixin`.
- **Clients:** Website public Onahar page + homepage stats; customer account Onahar section; Admin Panel Onahar settings and distribution CRUD.
- **Ops:** Monthly cycle job (management command / scheduler) must run idempotently at month boundary.
- **Docs/tests:** `onahar/docs/backend/`, `onahar/docs/frontend/`, and API tests for auth, privacy, fund integrity, duplicate prevention, and monthly math.
