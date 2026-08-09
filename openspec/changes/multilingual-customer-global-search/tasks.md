## 1. App scaffold and models

- [x] 1.1 Create `search` Django app package (`models`, `services`, `api`, `admin`, `tests`, `docs`) and register it in `INSTALLED_APPS`
- [x] 1.2 Implement `SearchDocument` model (`public_id`, `document_type`, `title_en`, `title_bn`, short description, image/price/availability fields, source links, `is_active`, `popularity_score`, timestamps)
- [x] 1.3 Implement `SearchKeyword` model (FK document, `keyword` normalized, `keyword_raw`, `locale_hint`, unique per document+keyword)
- [x] 1.4 Implement `SearchQueryEvent` and `SearchClickEvent` models with indexes for analytics (normalized query, zero-result, created_at)
- [x] 1.5 Generate and apply migrations; register models in Django admin for ops fallback

## 2. Normalization, matching, and ranking services

- [x] 2.1 Implement `normalize_query` (trim, collapse spaces, strip ignorable punctuation, lowercase Latin, preserve Bangla, Unicode NFC) with unit tests
- [x] 2.2 Implement matching service: exact, starts-with, partial/substring, keyword/synonym, fuzzy (rapidfuzz or difflib wrapper) with configurable thresholds
- [x] 2.3 Implement ranking per design priority + popularity/`public_id` tie-break; support `limit` default 8 / max 20 and optional `type` filter
- [x] 2.4 Implement weak/empty recovery helpers (`did_you_mean`, `related`) when strong matches are missing
- [x] 2.5 Add optional short-TTL cache for active documents+keywords with invalidate-on-admin-write hook

## 3. Catalog sync and seed data

- [x] 3.1 Implement bootstrap/upsert sync from active `MealCategory` packages and customer-visible `Ingredient` (and category facet documents) without wiping curated keywords
- [x] 3.2 Seed common Bangla/Banglish/English keyword packs (rice/kacchi/chicken/etc.) via data migration, fixture, or management command
- [x] 3.3 Add management command to re-run sync; document when to run after meal renames

## 4. Customer search and suggestions APIs

- [x] 4.1 Implement serializers for search/suggestion result cards (`type`, `public_id`, names, optional image/price/availability/short_description)
- [x] 4.2 Implement `GET /api/v1/search/` with normalization, ranking, recovery fields, validation, and throttling
- [x] 4.3 Implement `GET /api/v1/search/suggestions/` with min normalized length 2, lean payload, default limit 6
- [x] 4.4 Implement `GET /api/v1/search/popular/` from analytics aggregation and/or curated pins
- [x] 4.5 Mount routes in `core/urls.py`; add OpenAPI helpers with multilingual and typo examples

## 5. Analytics capture

- [x] 5.1 Auto-record (or best-effort record) `SearchQueryEvent` on search, including zero-result cases; never fail the search response on analytics errors
- [x] 5.2 Implement `POST /api/v1/search/events/click` for click-through tracking with `session_id` / optional auth
- [x] 5.3 Apply anonymous throttles on analytics write endpoints

## 6. Admin web APIs

- [x] 6.1 Implement verified-admin CRUD for documents under `/api/v1/web/search/documents/` (paginated list, filters `document_type`/`is_active`/`q`, create/retrieve/patch/deactivate)
- [x] 6.2 Implement keyword nest or sub-resource add/list/remove with normalization + uniqueness
- [x] 6.3 Implement analytics summaries: top queries, zero-result queries, top clicked documents with allowlisted date range + pagination
- [x] 6.4 Enforce verified-admin permissions; reject unsupported filters with `400`; add OpenAPI helpers

## 7. Tests

- [x] 7.1 Unit tests: normalization cases (`"  Kacchi  "`, Bangla `ভাত`, punctuation)
- [x] 7.2 Matching/ranking tests: exact first, partial `চিক`, synonyms `vat`/`bhat`/`rice`, fuzzy `kachci`/`chiken`, inactive excluded
- [x] 7.3 API tests: search multi-type payload, suggestions min length, popular guest access, click event validation, throttle smoke if practical
- [x] 7.4 Admin API permission + CRUD/keyword + zero-result analytics aggregation tests

## 8. Documentation

- [x] 8.1 Write `search/docs/backend/customer-global-search.md` (models, normalize/match/rank, APIs, analytics fields, error map, verify steps)
- [x] 8.2 Write `search/docs/frontend/customer-global-search.md` (debounce 250–350ms, min chars, grouping, dropdown limit, did-you-mean/related, recent localStorage, popular, click events, type routing)
- [x] 8.3 Write `search/docs/frontend/admin-search-catalog.md` (document/keyword management + analytics screens field mapping)
- [x] 8.4 Run relevant tests and fix failures; smoke-check new endpoints in OpenAPI/Swagger if available
