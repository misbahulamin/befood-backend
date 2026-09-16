## 1. Unblock Django boot

- [x] 1.1 Fix `wallet/api/web_views.py` OpenAPI `parameters=[...]` closer: change erroneous `),` to `],`
- [x] 1.2 Grep the repo for `build_subscription_search_q` and any other stale helper names; ensure callers only import `build_customer_people_q` / `build_subscription_people_q`
- [x] 1.3 Run AST/`compileall` on `user_management`, `orders`, `wallet`, and `support` (excluding migrations) and confirm zero `SyntaxError`s
- [x] 1.4 Run `python manage.py check` and confirm URL loading succeeds

## 2. Lock shared people-search module

- [x] 2.1 Confirm `user_management/services/admin_people_search.py` exports the canonical helpers and `looks_like_uuid` behavior per `admin-people-search` spec
- [x] 2.2 Verify `admin_customer.py`, `support/services/conversations.py`, `orders/filters.py`, and `wallet/api/web_views.py` all call the shared builders with correct prefixes
- [x] 2.3 Confirm admin subscription `q` filter uses `build_subscription_people_q` and applies `.distinct()` where joins can duplicate rows

## 3. API / OpenAPI / docs consistency

- [x] 3.1 Ensure admin wallet funding list OpenAPI documents the `q` query parameter
- [x] 3.2 Ensure admin subscription list OpenAPI and allowlisted query set include `q`
- [x] 3.3 Align already-touched frontend/backend docs for customer, subscription, and wallet funding search with the shared `q` behavior (no stale helper names)

## 4. Regression coverage

- [x] 4.1 Add focused unit tests for `looks_like_uuid`, empty `q`, phone normalization path, and subscription `public_id` composition
- [x] 4.2 Add a smoke import test (or equivalent) that imports `orders.filters` and `wallet.api.web_views` successfully
- [x] 4.3 Run the new tests and a quick admin `q` smoke against customers / subscriptions / wallet-funding / support if the local server is available

## 5. Hotfix hygiene

- [x] 5.1 Keep unrelated WIP (`db.sqlite3`, credential-linking churn outside this change) out of the hotfix commit unless explicitly requested
- [x] 5.2 Re-run `python manage.py check` as the final gate before considering the change apply-complete
