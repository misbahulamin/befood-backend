## Why

On branch `production-hotfix`, unfinished admin people-search work left Django unable to boot: first an `ImportError` for a renamed helper (`build_subscription_search_q` vs `build_subscription_people_q`), then a `SyntaxError` in `wallet/api/web_views.py` that closes `parameters=[...]` with `)` instead of `]`. The ASGI server dies during URL checks, so every API is down until these are fixed.

## What Changes

- Fix the broken `extend_schema(parameters=[...])` bracket in `wallet/api/web_views.py` (`),` → `],`).
- Lock a single canonical public API for shared admin people-search helpers in `user_management/services/admin_people_search.py` (`build_customer_people_q`, `build_subscription_people_q`) and align all callers.
- Verify no remaining stale import names or syntax errors across the touched admin-search surfaces (customers, support inbox, subscriptions, wallet funding).
- Restore `python manage.py check` / `runserver` boot on `production-hotfix`.
- Add a small regression guard (compile/import check and/or focused unit coverage for the helper module and caller imports).

## Capabilities

### New Capabilities

- `admin-people-search`: Shared verified-admin free-text people search (name/email/username/phone normalization + exact `public_id` UUID) reused by customer directory, support inbox, subscription board, and wallet funding review.

### Modified Capabilities

- `admin-customer-directory`: Customer list `q` search MUST use the shared people-search behavior (username, multi-word name, and exact customer `public_id` when `q` is a canonical UUID), not only the older name/email/phone subset.
- `wallet-funding`: Admin funding-request list MUST support allowlisted `q` people-search against the related customer (and document OpenAPI query param).

## Impact

- **Boot / ops:** Unblocks local and any deploy of `production-hotfix` currently failing URL import.
- **Code:** `wallet/api/web_views.py`, `orders/filters.py`, `user_management/services/admin_people_search.py` (new), `user_management/services/admin_customer.py`, `support/services/conversations.py`, subscription admin OpenAPI/`q` wiring, related docs already drafted on the branch.
- **APIs (additive):** Admin subscription list and admin wallet funding list gain/confirm `q`; customer directory search becomes slightly richer (username, UUID, multi-word name) via the shared helper — backward compatible for existing `q` clients.
- **Out of scope:** Unrelated WIP on `unfinished-features` (referral/wallet dual-bucket), credential-linking test churn, and committing secrets/`db.sqlite3`.
