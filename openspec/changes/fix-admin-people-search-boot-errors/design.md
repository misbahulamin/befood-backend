## Context

On `production-hotfix`, admin list UIs were being unified behind `user_management/services/admin_people_search.py` so customer directory, support inbox, subscription board, and wallet funding review share the same `q` matching rules.

Terminal evidence showed a failure cascade:

1. **ImportError (rename thrash):** Callers briefly imported `build_subscription_search_q` while the module exported `build_subscription_people_q` (and vice versa during edits). Django URL loading (`orders.filters` → `orders.api.views` → `core.urls`) failed, so the whole ASGI process crashed during system checks.
2. **SyntaxError (current blocker):** In `wallet/api/web_views.py`, an OpenAPI `parameters=[...]` list was closed with `),` instead of `],` when inserting the `q` parameter. Confirmed by `ast.parse` / `py_compile` — this is the only remaining syntax error in the touched apps.
3. **Import graph risk:** Any caller mismatch against the helper public names will again kill boot, because these modules are imported at URL include time.

Current helper surface (intended canonical):

- `build_customer_people_q(q, *, customer_prefix='')`
- `build_subscription_people_q(q)` (customer fields via `customer__` + subscription `public_id`)

## Goals / Non-Goals

**Goals:**

- Restore Django boot (`manage.py check` / `runserver`) on this branch.
- Freeze one helper naming convention and align every caller.
- Preserve shared search semantics (phone normalization, multi-word name, username, exact UUID `public_id`).
- Add a light regression guard so a bad rename or bracket typo is caught before deploy.

**Non-Goals:**

- Shipping referral / dual-bucket wallet work from `unfinished-features`.
- Broad search-product redesign (fuzzy ranking, full-text indexes).
- Changing auth/permission models on admin endpoints.
- Resolving unrelated `phone_availability` / credential-linking diffs unless they block boot.

## Decisions

### 1. Fix syntax first, then verify imports

- **Choice:** Correct `parameters=[...]` closing bracket in `wallet/api/web_views.py`, then run AST compile + `manage.py check`.
- **Why:** ImportError is already resolved in the working tree (all callers use `build_*_people_q`); boot is blocked only by the SyntaxError.
- **Alternative:** Revert the entire people-search diff — rejected because the feature work is mostly correct and additive.

### 2. Canonical names: `*_people_q`, never `*_search_q`

- **Choice:** Keep `build_customer_people_q` / `build_subscription_people_q`. Do not reintroduce aliases unless a short deprecation shim is required for an already-shipped import (not the case here; module is new/untracked).
- **Why:** Matches current callers and avoids dual-name drift that already caused the ImportError loop.
- **Alternative:** Alias both names forever — rejected; increases rename confusion.

### 3. Shared helper module owns matching rules; call sites only pass prefixes

- **Choice:** Call sites pass `customer_prefix` (`''`, `customer__`, `wallet__customer__`) and OR any domain-only fields (e.g. support `last_message__icontains`, subscription own `public_id` via `build_subscription_people_q`).
- **Why:** Keeps phone/`looks_like_uuid` logic in one place; prevents divergent admin `q` behavior.
- **Alternative:** Duplicate Q builders per app — rejected; that is what caused inconsistent search before.

### 4. UUID matching only for canonical 36-char form

- **Choice:** Keep `looks_like_uuid` rejecting short hex / phone-like strings that `uuid.UUID` would zero-pad.
- **Why:** Prevents accidental `public_id` matches on numeric phone fragments.
- **Alternative:** Accept any `uuid.UUID`-parseable string — rejected as unsafe for phone search.

### 5. Regression guard = compile/import + focused helper tests

- **Choice:** (a) `python -m compileall` / AST scan on touched packages; (b) unit tests for helper Q construction and that caller modules import successfully; (c) `manage.py check`.
- **Why:** Boot failures here are import-time; expensive full API suite is not required to catch this class of bug.
- **Alternative:** Only manual runserver — rejected for hotfix reliability.

## Risks / Trade-offs

- **[Risk] Similar bracket typos in other `extend_schema` edits** → Mitigation: one-time AST scan of `user_management`/`orders`/`wallet`/`support` during apply; keep OpenAPI list closers as `],`.
- **[Risk] Stale docs or OpenAPI still mention old helper names** → Mitigation: grep for `build_subscription_search_q` and update docs already touched on the branch.
- **[Risk] Richer customer `q` (username/UUID) surprises clients expecting only name/email/phone** → Mitigation: additive only; document in admin customer / funding / subscription frontend docs.
- **[Risk] Mixing this hotfix with unrelated WIP files** → Mitigation: apply only boot + people-search related files; leave credential-linking / sqlite out of the commit unless explicitly requested.
- **[Trade-off] Shared OR filters can be broader (more hits)** → Acceptable for admin UX; keep `distinct()` on subscription filter where JOINs can duplicate rows.

## Migration Plan

1. Apply syntax fix and confirm import name consistency.
2. Run compileall + `manage.py check`.
3. Smoke: admin customers `?q=`, subscriptions `?q=`, wallet-funding `?q=`, support conversations search.
4. Deploy `production-hotfix` only after check passes.
5. Rollback: revert the single syntax/import commit if needed; helper module is additive.

## Open Questions

- None blocking apply. Optional later: extract OpenAPI shared `q` parameter description constant to avoid copy-paste drift across admin list schemas.
