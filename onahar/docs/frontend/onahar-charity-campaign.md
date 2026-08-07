# Frontend: Onahar Charity Campaign

## Summary

Implement BeFood’s **অনাহার** surfaces against the APIs below. All meal/fund numbers come from the backend—never hard-code marketing totals.

**Clients:** public website (no login), customer account (token), Admin Panel (verified admin token).

## Auth

```http
Authorization: Token <token>
```

Public routes need **no** auth header.

## Feature overview

Tagline: **“আপনার ৫০ মিল, অনাহারের ১ মিল”** (target is admin-configurable).

- Each **delivered** meal slot → 1 Onahar point for that calendar month.
- When points reach the month’s target (and multiples), BeFood credits the global **Onahar Fund** with Onahar meals.
- Incomplete points **expire at month end** (no carry-forward).
- Admins publish distribution events with proof photos; fund decreases automatically.

## User flows

### Public visitor

1. Homepage teaser → `GET /onahar/stats/` → show contributed / distributed / CTA.
2. Public Onahar page → stats + leaderboard + ledger + distribution list.
3. Distribution card → detail with gallery.

### Logged-in customer

1. Account → Onahar → `GET /onahar/me/` → progress bar `current_points / target`.
2. History table → `GET /onahar/me/history/`.
3. Privacy control → `GET|PATCH /onahar/me/privacy/` (`public` | `partial` | `anonymous`).

### Admin

1. Settings → read/update target; show history.
2. Create draft distribution → upload media → publish (fails if fund insufficient).
3. Cancel published → fund restored.
4. Fund + audit logs for ops.

## Page structures

### Homepage teaser

Reuse stats fields:

- `total_meals_contributed`
- `total_meals_distributed`
- CTA → `/onahar` (or your public route)

### Public Onahar Page

1. Hero + emotional copy  
2. Overall statistics  
3. Contributor leaderboard  
4. Transparency ledger  
5. “আমরা কোথায় খাবার পৌঁছে দিয়েছি” distribution list  

### Customer dashboard

- Progress: `{current_points} / {target}` + `points_to_next_contribution`
- Lifetime: eligible meals, contributed meals, ranking
- History table by month

### Admin

- Target form + history
- Distributions table (filter `status`)
- Distribution editor (draft only for meal count)
- Publish / Cancel actions
- Fund summary widget

## API contracts

Base URLs assume same host as other BeFood APIs.

### `GET /onahar/stats/` (public)

```json
{
  "total_meals_contributed": 12540,
  "total_meals_distributed": 9870,
  "available_meals": 2670,
  "total_contributors": 842,
  "total_distribution_campaigns": 18,
  "current_month_contributions": 120,
  "current_contribution_target": 50
}
```

### `GET /onahar/leaderboard/?page=1&page_size=20` (public)

Paginated `{ count, next, previous, results }`:

```json
{
  "rank": 1,
  "display_name": "R*** A***",
  "total_meals": 24
}
```

Never expect email/phone/user id.

### `GET /onahar/ledger/` (public)

```json
{
  "entry_side": "contribution",
  "occurred_at": "2026-08-01T10:00:00+06:00",
  "meals": 1,
  "display_name": "Anonymous Contributor",
  "location": null,
  "campaign_public_id": null,
  "campaign_title": null
}
```

or distribution side with `location`, `campaign_public_id`, `campaign_title`.

### `GET /onahar/distributions/` / `GET /onahar/distributions/{public_id}/` (public)

List cards: `public_id`, `title`, `location`, `distribution_date`, `meals_distributed`, `description`, `cover_image_url`.  
Detail adds `full_address`, `beneficiary_info`, `media[]` with `image_url`.

Drafts are never returned.

### `GET /onahar/me/` (customer)

```json
{
  "year_month": "2026-08",
  "current_points": 32,
  "target": 50,
  "contributions_earned": 0,
  "remaining_points": 32,
  "points_to_next_contribution": 18,
  "status": "open",
  "total_eligible_meals": 210,
  "total_onahar_meals_contributed": 4,
  "current_ranking": 12
}
```

### `GET /onahar/me/history/` (customer)

```json
{
  "year_month": "2026-07",
  "net_points": 54,
  "target_snapshot": 50,
  "contributions_earned": 1,
  "expired_points": 4,
  "remaining_or_expired_points": 4,
  "status": "closed",
  "closed_at": "2026-08-01T00:15:00+06:00",
  "created_at": "...",
  "updated_at": "..."
}
```

### `GET|PATCH /onahar/me/privacy/` (customer)

```json
{ "display_mode": "partial", "updated_at": "..." }
```

PATCH body: `{ "display_mode": "anonymous" }` — invalid values → `400`.

### Admin settings

`GET|PATCH /api/v1/web/onahar/settings/`

```json
{
  "contribution_target": 50,
  "total_contributed_meals": 1500,
  "total_distributed_meals": 900,
  "available_meals": 600,
  "updated_at": "..."
}
```

PATCH: `{ "contribution_target": 45 }`

History: `GET /api/v1/web/onahar/settings/history/`

### Admin fund & audit

- `GET /api/v1/web/onahar/fund/`
- `GET /api/v1/web/onahar/audit-logs/?action=target_changed`

### Admin distributions

| Action | Method | Path |
|--------|--------|------|
| List / create draft | GET / POST | `/api/v1/web/onahar/distributions/` |
| Detail / patch draft | GET / PATCH | `/api/v1/web/onahar/distributions/{public_id}/` |
| Publish | POST | `.../publish/` |
| Cancel | POST | `.../cancel/` |
| Upload image | POST multipart | `.../media/` field `image` |

Create body example:

```json
{
  "title": "ঢাকা রেলওয়ে স্টেশন খাদ্য বিতরণ",
  "location": "Kamalapur Railway Station",
  "full_address": "...",
  "distribution_date": "2026-08-15",
  "meals_distributed": 250,
  "description": "...",
  "beneficiary_info": ""
}
```

Publish with insufficient fund → **409** `{ "detail": "...", "error_code": "INSUFFICIENT_ONAHAR_FUND" }`.

Meal count is **immutable after publish** (cancel + new draft if wrong).

## Pagination / filtering

- Standard DRF: `page`, `page_size` (max 100), response `count/next/previous/results`.
- Admin distribution list: optional `?status=draft|published|cancelled`.

## Monthly calculation (UI copy)

- Progress resets each calendar month.
- Example: target 45, customer ends month at 40 → **0 contribution**, 40 points expire; next month starts at 0.
- 120 points with target 50 → **2 contributions**, 20 expire at month close.
- Crossing a multiple **mid-month** credits the fund immediately (celebrate in UI).

Suggested congrats copy when `contributions_earned` increases:

> অভিনন্দন! আপনার এই মাসের খাবারগুলো একজন মানুষের এক বেলার আহারে রূপ নিয়েছে।

## UI states

- Loading skeletons for stats/leaderboard
- Empty leaderboard / no distributions yet
- 401 → login; 403 → permission; 409 publish → show fund shortfall
- Image upload errors: type/size validation messages from `detail`

## Media

Admin uploads via multipart `image` (JPEG/PNG/WebP/GIF, max 5MB). Public responses expose absolute `image_url` / `cover_image_url`.
