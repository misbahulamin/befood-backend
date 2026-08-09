# Customer Global Search Bar (Frontend)

## Summary

Wire the website global search bar to BeFood’s backend search APIs. Ranking, multilingual synonyms, and typo tolerance are **server-side**. The client debounces input, groups results by `type`, and navigates with `public_id`.

**Clients:** web (primary), mobile can reuse the same lean payloads.

## Endpoints

Base: `/api/v1/search/`

| Call | When |
| --- | --- |
| `GET /api/v1/search/popular/` | Search box focused, query empty |
| `GET /api/v1/search/suggestions/?q=` | Typing, normalized length ≥ 2 |
| `GET /api/v1/search/?q=` | Explicit search / “view all” / Enter |
| `POST /api/v1/search/events/click/` | User selects a result |

Auth: guest-friendly (`AllowAny`). Optional `Authorization` when logged in (improves analytics user linkage). Optional `X-Guest-Session-Id` or `session_id` query/body.

## Integration steps

1. On focus + empty input → load popular terms; show **Recent Searches** from `localStorage` (client-only in v1).
2. Debounce keystrokes **250–350ms** before calling suggestions/search.
3. Call suggestions only when trimmed query length ≥ **2**.
4. Render dropdown with **5–8** best results (API default 8). Group by `type` (Meals / Packages / Foods / Categories).
5. On select → `POST /events/click/` then route by `type` + `public_id`.
6. Persist query string into recent searches (cap ~8); allow Clear.
7. If `results` empty but `did_you_mean` / `related` present → show recovery UI, not a dead “No Result”.

## Request / response examples

### Search

`GET /api/v1/search/?q=kacchi&limit=8`

```json
{
  "query": "kacchi",
  "query_normalized": "kacchi",
  "results": [
    {
      "type": "food",
      "public_id": "11111111-1111-1111-1111-111111111111",
      "name": "কাচ্চি বিরিয়ানি",
      "name_en": "Kacchi Biryani",
      "short_description": "",
      "image_url": "",
      "price": null,
      "currency": "BDT",
      "is_available": true,
      "deep_link_hint": "food_detail"
    }
  ],
  "did_you_mean": null,
  "related": []
}
```

### Suggestions

`GET /api/v1/search/suggestions/?q=ka`

Lean cards: `type`, `public_id`, `name`, `name_en`.

### Click

```json
POST /api/v1/search/events/click/
{
  "public_id": "11111111-1111-1111-1111-111111111111",
  "query": "kacchi",
  "position": 0,
  "session_id": "guest-uuid"
}
```

## Type-based routing

| `type` | Suggested route |
| --- | --- |
| `package` | Package / meal plan detail by `public_id` |
| `instant_meal` | Instant/daily meal detail |
| `food` | Food / dish detail or menu highlight |
| `category` | Category browse (Monthly Package, Instant Meal, …) |

Prefer `public_id` from the search payload; do not invent integer PKs.

## UI states

| State | UI |
| --- | --- |
| Empty focus | Popular + Recent |
| Typing (<2 chars) | No suggest call |
| Has results | Grouped list; optional “View all” |
| No strong results | `did_you_mean` + `related` |
| Error / throttle | Soft toast; keep last good dropdown |

## Card fields

Ideal: image, name, type, short description, price, availability. All except `type` / `public_id` / `name` may be empty—render gracefully.
