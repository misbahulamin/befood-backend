# Admin Search Catalog (Frontend)

## Summary

Verified-admin UI for managing searchable documents, Bangla/Banglish/English keywords, and reading search analytics (especially zero-result demand).

**Auth:** Token + verified admin (`IsVerifiedAdmin`). Base: `/api/v1/web/search/`.

## Screens

### 1. Documents table

`GET /api/v1/web/search/documents/?document_type=&is_active=&q=&page=&page_size=`

Columns: title_en, title_bn, type, active, available, popularity, updated_at.

Filters must be allowlisted only (`document_type`/`type`, `is_active`, `q`, pagination). Unknown params → `400`.

### 2. Document create / edit

`POST /api/v1/web/search/documents/`

```json
{
  "document_type": "food",
  "title_en": "Kacchi Biryani",
  "title_bn": "কাচ্চি বিরিয়ানি",
  "short_description": "",
  "is_active": true,
  "keywords": [
    {"keyword_raw": "kacchi", "locale_hint": "banglish"},
    {"keyword_raw": "কাচ্চি", "locale_hint": "bn"}
  ]
}
```

`PATCH /api/v1/web/search/documents/{public_id}/` for partial updates.

`DELETE` soft-deactivates (`is_active=false`).

### 3. Keywords panel

`GET/POST /api/v1/web/search/documents/{public_id}/keywords/`

`DELETE /api/v1/web/search/documents/{public_id}/keywords/{keyword_public_id}/`

`locale_hint`: `bn` | `en` | `banglish` | `other`.

Duplicate normalized keyword → `422` `DUPLICATE_KEYWORD`.

### 4. Analytics

`GET /api/v1/web/search/analytics/?from=&to=`

Response shape:

```json
{
  "top_queries": [{"query": "chicken", "count": 42}],
  "zero_result_queries": [{"query": "tehari", "count": 240}],
  "top_clicked": [
    {
      "public_id": "...",
      "title_en": "Kacchi Biryani",
      "type": "food",
      "count": 18
    }
  ]
}
```

Prioritize zero-result table for product decisions (missing dishes/packages).

## Field mapping

| UI field | API field |
| --- | --- |
| Type | `document_type` |
| English title | `title_en` |
| Bangla title | `title_bn` |
| Keyword text | `keyword_raw` (server stores normalized `keyword`) |
| Popularity | `popularity_score` |
| Active | `is_active` |

## Ops note

After bulk meal renames in Meals admin, ask backend to run:

`python manage.py sync_search_catalog --seed-keywords`

Sync refreshes titles from meals/ingredients but keeps curated keywords.
