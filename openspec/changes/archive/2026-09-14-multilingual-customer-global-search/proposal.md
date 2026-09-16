## Why

BeFood customers browse packages, meals, and food items through a global search bar, but the backend has no unified, typo-tolerant, multilingual search. Customers type Bangla, Banglish, or English (and common misspellings); without normalization, synonyms, and ranked multi-type results, discovery fails and product demand signals are lost.

## What Changes

- Add a dedicated **customer global search** domain that indexes searchable catalog documents (packages, instant/daily meals, food/menu items, categories) with Bangla / English names and managed keyword synonyms (Banglish variants included).
- Expose a **public/customer search API** that normalizes the query (case, whitespace, punctuation, Unicode), then ranks matches via exact → starts-with → keyword/synonym → fuzzy strategies in one response.
- Expose a **suggestions / autocomplete API** (min character threshold + server-side debounce guidance for clients) returning a short ranked list for the search dropdown.
- Support **empty-query UX helpers**: popular / trending searches derived from analytics; recent search remains primarily client-side (local storage) with optional click/query telemetry.
- Persist **search analytics** (original query, normalized query, result counts, zero-result flag, clicked result, user/session) so product can see demand, typos, and missing catalog gaps.
- Add **admin APIs** to manage searchable documents and keyword synonyms without code deploys.
- Ship **frontend contract docs** for the global search bar: debounce, grouping by type, no-result / “did you mean”, popular & recent searches, and navigation by result `type` + `public_id`.
- Prefer **backend search logic** for production scale; frontend fuzzy libraries are not the source of truth.
- **Out of scope for this change:** Elasticsearch/OpenSearch/Meilisearch cluster ops, account-synced cross-device search history, personalized ranking ML, voice search, admin full-text over blogs/FAQ/notices, replacing existing per-resource `search`/`q` admin filters.

## Capabilities

### New Capabilities
- `search-catalog`: Searchable catalog documents and keyword/synonym sets (BN/EN/Banglish) managed in the database and linked to packages, meals, food items, and categories.
- `customer-global-search`: Normalized multi-type search API with exact/partial/synonym/fuzzy matching, stable ranking, and compact result cards for the dropdown and full-results page.
- `search-suggestions`: Autocomplete/suggestion endpoint for short prefixes after a minimum character threshold.
- `search-discovery-helpers`: Popular/trending search terms for empty focus state; documented recent-search client behavior.
- `search-analytics`: Persist query and click events (including zero-result queries) for product analytics.
- `search-admin-api`: Verified-admin web APIs to CRUD searchable documents, keywords, and review analytics summaries.
- `search-frontend-docs`: Customer global search bar UI/API contract (debounce, grouping, no-result, popular/recent, navigation).

### Modified Capabilities
- _(none)_ — existing meal list `?search=` and other admin `search`/`q` filters remain as-is; this change adds a dedicated customer discovery surface rather than altering those contracts.

## Impact

- **New app** (recommended): `search/` (or `catalog_search/`) with models (documents, keywords, query events), services (normalize, match, rank, suggest, analytics), customer/shared endpoints, web admin routes under `/api/v1/web/…`, tests, `docs/backend` + `docs/frontend`.
- **Meals / ingredients:** Index active `MealCategory` packages (Student/Regular/Professional/Family/monthly/etc.), customer-visible food items (`Ingredient` and/or published menu dish labels), and category-like facets; keep integer PKs internal and expose `public_id` on results.
- **Clients:** `befood_frontend` global search bar consumes search + suggestions + popular endpoints; navigates by `type` + `public_id`.
- **Auth:** Search/suggest/popular are public or lightly throttled; analytics may accept anonymous `session_id` and optional authenticated `user_id`; admin mutations require verified admin / group permissions.
- **Dependencies:** In-process fuzzy matching for v1 (e.g. rapidfuzz / difflib) plus DB keyword tables—no external search cluster required for the first release; design may note a future migration path.
- **Docs/tests:** Backend technical docs, frontend contracts, OpenAPI, and tests for normalization, ranking, multilingual synonyms, typos, empty/zero-result, suggestions debounce contract, and analytics capture.
