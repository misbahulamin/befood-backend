## Context

The customer website has a global search bar, but BeFood’s backend only offers narrow per-resource filters (e.g. meal list `?search=`). Catalog entities today are primarily `MealCategory` (packages / meal offerings) and `Ingredient` (food items shown on menus). Names are largely English-oriented; there is no synonym/keyword store for Bangla or Banglish, no typo tolerance, and no unified multi-type discovery API.

Customers naturally search with mixed scripts and spellings (`ভাত` / `vat` / `bhat` / `rice`, `কাচ্চি` / `kacchi` / `kachci`). Product also wants autocomplete, popular searches, “did you mean” / related results when exact hits are weak, and analytics (especially zero-result queries) to guide menu expansion.

Constraints:

- Business logic in `services/`; thin DRF views; public identities via `public_id`.
- Customer/shared APIs under `/api/v1/…`; admin under `/api/v1/web/…`.
- Multi-client: lean mobile-safe payloads; web may show richer cards (image, price, short description).
- Prefer backend ranking as source of truth (not Fuse.js-only frontend search).
- This repo ships backend + client contract docs; React UI lives in the frontend repo.

## Goals / Non-Goals

**Goals:**

- Searchable catalog documents with `name_bn`, `name_en`, keyword synonyms, result `type`, and link to source entity.
- Query normalization + multi-strategy matching (exact, starts-with/partial, keyword/synonym, fuzzy) with deterministic ranking.
- One search response mixing packages, instant/daily meals, food items, and categories.
- Suggestions API for autocomplete; popular-searches helper for empty focus.
- Analytics events for queries and clicks (including zero-result).
- Admin CRUD for documents/keywords + analytics summaries.
- Frontend docs covering debounce (250–350ms), grouping, no-result UX, recent (local) + popular searches.

**Non-Goals:**

- External search engine cluster (Elasticsearch / Meilisearch / OpenSearch) in v1.
- Cross-device synced account search history (localStorage is enough for v1).
- Searching blogs, FAQ, notices, or admin ops catalogs.
- ML personalization or A/B ranking.
- Replacing existing admin list `search`/`q` parameters on other modules.

## Decisions

### 1. New app: `search/`
- **Choice:** Create `search/` with models, services (`normalize`, `matching`, `ranking`, `indexing`, `analytics`, `suggestions`), `api/` (customer + web), tests, docs. Mount:
  - Customer: `/api/v1/search/`, `/api/v1/search/suggestions/`, `/api/v1/search/popular/`, `/api/v1/search/events/` (click/query telemetry).
  - Admin: `/api/v1/web/search/documents/`, `/api/v1/web/search/analytics/`.
- **Rationale:** Cross-cutting discovery over meals/ingredients without overloading `meals` views; mirrors `service_area` bounded-context pattern.
- **Alternatives considered:**
  - Only extend `meals` filters — cannot unify types or analytics cleanly.
  - Frontend-only Fuse.js over a bulk dump — poor scale, weak analytics, stale synonyms.

### 2. Catalog model: `SearchDocument` + `SearchKeyword`
- **Choice:**
  - `SearchDocument`: `public_id`, `document_type` (`package` | `instant_meal` | `food` | `category`), `title_en`, `title_bn`, `subtitle` / `short_description`, optional `image_url` or media ref, optional `price` snapshot fields, `is_active`, `is_available`, `popularity_score`, generic FK or typed nullable FKs to `MealCategory` / `Ingredient` / category key, timestamps.
  - `SearchKeyword`: FK document, `keyword` (normalized form stored), `keyword_raw` (display/original), `locale_hint` (`bn` | `en` | `banglish` | `other`), unique per `(document, keyword)`.
- **Rationale:** Admin can manage synonyms (`vat`, `bhat`, `rice`) without code deploys; ranking reads one denormalized document table for speed.
- **Alternatives considered:** Search live off `MealCategory.meal_name` only — fails multilingual/typo goals. JSON keywords-only column — harder to index/admin filter.

### 3. Indexing / sync strategy
- **Choice:** v1 = **explicit documents** maintained by admin + **bootstrap sync** management command/service that upserts documents from active `MealCategory` and customer-visible `Ingredient` (and seeded category facets like “Monthly Package”, “Student Package”). On meal/ingredient save, optional signal or service hook refreshes linked document titles; keywords remain admin-managed and are not wiped on sync.
- **Rationale:** Packages/ingredients already exist; synonyms need human curation for Banglish variants.
- **Alternatives considered:** Fully automatic keyword generation from transliteration libs — useful later as assistive suggestions, not sole source in v1.

### 4. Query normalization pipeline
- **Choice:** `normalize_query(raw) →` trim, collapse whitespace, strip most punctuation, Unicode NFC, lowercase for Latin letters, preserve Bangla letters, map common Banglish punctuation noise. Store both `query_original` and `query_normalized` on analytics. Empty after normalize → empty results / popular-only UX (no 500).
- **Rationale:** Matches product examples (`"  Kacchi  "` → `kacchi`) and keeps matching deterministic.
- **Alternatives considered:** Aggressive phonetic encoding (Soundex) on all tokens — weak for Bangla; use only as optional fuzzy assist later.

### 5. Matching & ranking
- **Choice:** Score candidates from active documents/keywords:
  1. Exact title (bn/en) or exact keyword
  2. Starts-with on title/keyword
  3. Partial/substring contains
  4. Synonym/keyword hit (already covered but weighted)
  5. Fuzzy similarity (rapidfuzz `WRatio` / `partial_ratio` or stdlib fallback) above threshold (e.g. ≥ 75)
  6. Tie-break: `popularity_score`, then title, then `public_id`
  Cap dropdown default to **8** results; support `limit` with max (e.g. 20) and optional `type` filter. Return `match_tier` for debugging/docs but not required on lean mobile payloads.
- **Rationale:** Product priority order; fuzzy last so typos never outrank exact “কাচ্চি”.
- **Alternatives considered:** Postgres `pg_trgm` only — not portable to SQLite local/dev; pair later for prod Postgres. Elasticsearch — deferred.

### 6. Multi-type response contract
- **Choice:** Unified list items:
  ```json
  {
    "type": "food",
    "public_id": "...",
    "name": "কাচ্চি বিরিয়ানি",
    "name_en": "Kacchi Biryani",
    "short_description": "...",
    "image_url": "...",
    "price": "180.00",
    "currency": "BDT",
    "is_available": true,
    "deep_link_hint": "food_detail"
  }
  ```
  Include `query` echo, optional `did_you_mean`, optional `related` when primary matches are empty/weak. Frontend routes by `type` + `public_id`.
- **Rationale:** One API for the global bar; avoids N round-trips.
- **Type mapping:**
  - `package` → monthly/weekly/etc. `MealCategory` plans (Student/Regular/Professional/Family)
  - `instant_meal` → daily / instant-style offerings when modeled as such
  - `food` → searchable dishes / customer-visible ingredients / curated food documents
  - `category` → browse facets (e.g. “Monthly Package”, “Instant Meal”)

### 7. Suggestions vs full search
- **Choice:** `GET /api/v1/search/suggestions?q=` requires normalized length ≥ **2** (configurable). Returns titles only (or ultra-lean cards), limit default **6**. Full `GET /api/v1/search?q=` allows ≥ **1** but docs recommend client debounce **250–350ms** and min 2 chars for suggest. Same ranking core shared in services.
- **Rationale:** Prevents noisy single-letter traffic; matches product guidance.

### 8. No-result / weak-result handling
- **Choice:** Never return only a bare empty list without helpers when fuzzy candidates exist: include `did_you_mean` (best fuzzy title) and/or `related` (top popular/similar documents). If truly empty, return empty `results` plus optional popular fallback list under `popular_searches` or `related`.
- **Rationale:** Product UX requirement; improves conversion on typos.

### 9. Popular searches & recent history
- **Choice:** `GET /api/v1/search/popular/` returns top normalized queries / curated pins from analytics (with admin override list optional). **Recent searches** stay client localStorage; backend does not store per-user recent lists in v1 beyond analytics events.
- **Rationale:** Popular needs aggregation; recent is UX state and cheap on the client.

### 10. Analytics
- **Choice:** `SearchQueryEvent` with `query_original`, `query_normalized`, `result_count`, `is_zero_result`, nullable `user`, `session_id`, `created_at`. `SearchClickEvent` with FK/query event or denormalized query fields, `clicked_document`, `clicked_type`, `position`. Search endpoint MAY auto-record query events (sampled or always); clicks via `POST /api/v1/search/events/click`. Throttle anonymous writes.
- **Rationale:** Zero-result mining (`tehari` × 240) is an explicit product goal.
- **Alternatives considered:** Log-only without tables — harder for admin summaries.

### 11. Admin API
- **Choice:** Verified-admin CRUD for documents and nested keywords; list filters (`type`, `is_active`, `q`); analytics summary (`top_queries`, `zero_result_queries`, `top_clicked`) with date range + pagination. Seed common Bangla food synonyms in a data migration or fixture.
- **Rationale:** Ops can fix “kachci → kacchi” without engineering.

### 12. Performance & caching
- **Choice:** Load active documents+keywords into a short-TTL cache (or per-process memory with invalidate-on-admin-write) for suggest/search hot path; keep result sets small. Apply DRF throttling on search/suggest/events.
- **Rationale:** Catalog size is modest at BeFood scale; avoids per-keystroke heavy ORM joins.

### 13. Dependency: rapidfuzz (optional)
- **Choice:** Prefer `rapidfuzz` if acceptable in project deps; otherwise implement a thin wrapper around `difflib.SequenceMatcher` with the same service interface so tests stay stable.
- **Rationale:** Better typo tolerance for Latin Banglish; Bangla exact/partial still relies on keywords + substring.

## Risks / Trade-offs

- **[Risk] Incomplete synonym coverage → missed Banglish hits** → Mitigation: seed common foods; admin keyword CRUD; mine zero-result analytics weekly.
- **[Risk] Fuzzy false positives (short queries)** → Mitigation: higher fuzzy threshold for len ≤ 3; prefer suggest only on prefix/keyword for very short `q`.
- **[Risk] Stale document titles after meal rename** → Mitigation: sync hook/command; admin can edit document independently.
- **[Risk] SQLite vs Postgres search quality differences** → Mitigation: keep matching in Python services for v1 portability.
- **[Risk] Analytics write volume from autocomplete** → Mitigation: record full search more eagerly than every suggestion; throttle; debounce documented for clients.
- **[Trade-off] Denormalized catalog vs live joins** → Slight sync complexity for much simpler ranking and multilingual keywords.

## Migration Plan

1. Add `search` app + migrations for documents, keywords, query/click events.
2. Seed baseline documents from active meals/ingredients + common keyword packs (rice/kacchi/chicken/etc.).
3. Ship customer search/suggest/popular/events endpoints + OpenAPI.
4. Ship admin document/keyword + analytics APIs.
5. Publish frontend docs; frontend wires global bar with debounce and type-based navigation.
6. Rollback: feature-flag or stop mounting URLs; tables can remain unused; no change to order/meal purchase paths.

## Open Questions

- Exact product mapping of “Instant Meal” vs `MealCategory.meal_type=daily` (confirm labels with product).
- Whether food results should deep-link to ingredient detail, today’s menu, or a curated dish page when no dedicated dish model exists.
- Whether authenticated users should later sync recent searches server-side (deferred).
- Whether production Postgres should later add `pg_trgm` indexes as an optimization behind the same service API.
