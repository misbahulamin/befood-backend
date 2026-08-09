# Customer Global Search (Backend)

## Quick summary

BeFood global search indexes packages, instant meals, foods, and category facets into `SearchDocument` rows with Bangla / English / Banglish keywords. Customer APIs normalize the query, rank with exact → starts-with → partial → fuzzy, and record analytics (including zero-result queries).

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/search/?q=` | Guest OK | Ranked multi-type search |
| GET | `/api/v1/search/suggestions/?q=` | Guest OK | Autocomplete (min 2 chars) |
| GET | `/api/v1/search/popular/` | Guest OK | Popular / pinned terms |
| POST | `/api/v1/search/events/click/` | Guest OK | Click analytics |
| GET/POST | `/api/v1/web/search/documents/` | Verified admin | Document CRUD |
| GET/PATCH/DELETE | `/api/v1/web/search/documents/{public_id}/` | Verified admin | Document detail / deactivate |
| GET/POST | `/api/v1/web/search/documents/{public_id}/keywords/` | Verified admin | Keyword list/add |
| DELETE | `/api/v1/web/search/documents/{public_id}/keywords/{keyword_public_id}/` | Verified admin | Remove keyword |
| GET | `/api/v1/web/search/analytics/` | Verified admin | Top / zero-result / clicks |

## Permissions

| Endpoint group | Permission |
| --- | --- |
| Customer search/suggest/popular/click | `AllowAny` + anon throttles |
| Admin documents/keywords/analytics | `IsVerifiedAdmin` |

## Key models

- **SearchDocument** — `document_type` (`package` \| `instant_meal` \| `food` \| `category`), `title_en`, `title_bn`, card fields, optional FKs to `MealCategory` / `Ingredient`, `category_key`, `is_active`, `popularity_score`
- **SearchKeyword** — normalized `keyword` + `keyword_raw` + `locale_hint`, unique per document
- **SearchQueryEvent** / **SearchClickEvent** — analytics
- **PopularSearchPin** — admin-curated empty-focus terms

## Matching pipeline

1. `normalize_query` — NFC, trim, collapse spaces, casefold, strip punctuation (Bangla kept)
2. Score each active document against titles + keywords
3. Rank tiers: exact (0) → starts-with (1) → partial (2) → fuzzy (4)
4. Tie-break: higher `popularity_score`, then `title_en`, then `public_id`
5. Defaults: search limit 8 (max 20); suggestions limit 6 (max 12); suggestions require normalized length ≥ 2
6. Weak/empty recovery: `did_you_mean` + `related`

Fuzzy uses `difflib.SequenceMatcher` (threshold 75; 85 when query length ≤ 3).

## Catalog sync

```bash
python manage.py sync_search_catalog
python manage.py sync_search_catalog --seed-keywords
```

Upserts from active `MealCategory` and customer-visible `Ingredient`, plus category facets. **Does not wipe curated keywords.** Re-run after meal renames.

## Analytics fields

Query event: `query_original`, `query_normalized`, `result_count`, `is_zero_result`, optional `user`, `session_id`, `created_at`.

Click event: document + type + optional `position` / query / session.

Search GET auto-records query events best-effort (failures never break the response).

## Error map

| HTTP | error_code | When |
| --- | --- | --- |
| 400 | `VALIDATION_ERROR` | Missing `q` |
| 400 | `UNSUPPORTED_FILTER` | Bad `type` or unknown admin filter |
| 404 | `NOT_FOUND` | Unknown document/keyword/click target |
| 422 | `DUPLICATE_KEYWORD` | Keyword already on document |
| 401/403 | — | Admin endpoints without verified admin |

## How to verify

1. `python manage.py sync_search_catalog --seed-keywords`
2. `GET /api/v1/search/?q=vat` → Rice
3. `GET /api/v1/search/?q=kachci` → Kacchi recovery / fuzzy
4. `GET /api/v1/search/suggestions/?q=ka`
5. Admin: create document + keywords; `GET /api/v1/web/search/analytics/`
6. `python manage.py test search.tests.test_search`
