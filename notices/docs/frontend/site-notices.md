# Frontend — Site Notices

Backend overview: [`../backend/overview.md`](../backend/overview.md).

Admin management UI (Token auth): [`site-notices-admin.md`](site-notices-admin.md).

## What to build

1. On website load (or layout mount), call the public active feed.
2. If the list is empty → render nothing (or a silent empty state).
3. If one or more notices → show a banner / modal / stack using `severity` for styling.
4. Pick locale text from `title_en`/`body_en` or `title_bn`/`body_bn` (with fallback).

## Auth

**None.** Do not send `Authorization`. This endpoint is public for all visitors.

Target client: **web** (marketing / public site).

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| Load active notices | GET | `/notices/active/` |
| Paginate | GET | `/notices/active/?page=2&page_size=20` |

Default `page_size` is **20**; maximum **50** (values above max are capped by the API).

## Success response example

```http
GET /notices/active/
```

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "public_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "title_en": "Holiday hours",
      "title_bn": "ছুটির সময়সূচি",
      "body_en": "We are closed on Friday.",
      "body_bn": "শুক্রবার আমরা বন্ধ থাকব।",
      "severity": "warning",
      "publish_at": "2026-07-27T00:00:00Z",
      "publish_until": "2026-07-28T00:00:00Z",
      "sort_order": 0
    }
  ]
}
```

## Empty state

When nothing is active (no published notices, or all drafts/expired/scheduled):

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}
```

UI: hide the notice region entirely.

## Field meanings

| Field | Meaning |
|-------|---------|
| `public_id` | Stable id (use as React `key`) |
| `title_en` / `title_bn` | Titles; one may be empty |
| `body_en` / `body_bn` | Bodies; may be empty |
| `severity` | `info` \| `warning` \| `critical` |
| `publish_at` | Start time (UTC ISO-8601) or `null` |
| `publish_until` | End time (UTC ISO-8601) or `null` |
| `sort_order` | Display priority (lower first) |

Draft / unpublished flags are **not** returned. Only currently active notices appear.

## Locale selection

Recommended:

1. If site locale is `bn` and `title_bn` (or body) is non-empty → use BN fields.
2. Else if EN fields are non-empty → use EN.
3. Else fall back to whichever locale has text.

Always prefer filling **both** locales in Admin for production notices.

## Severity UI states

| `severity` | Suggested UI |
|-------------|--------------|
| `info` | Neutral / brand banner |
| `warning` | Emphasized / amber banner |
| `critical` | Strong / blocking or top-sticky alert |

Multiple notices: render in API order (`sort_order` then newest). Keep the stack compact (e.g. one primary + “N more”).

## Why this API

Admins publish time-bound bilingual announcements from Django Admin. The website needs a single unauthenticated read so every visitor sees the same live message without login.

## Integration checklist

- [ ] Fetch on public layout mount
- [ ] Handle empty `results`
- [ ] Locale fallback EN ↔ BN
- [ ] Style by `severity`
- [ ] Use `public_id` as list key
- [ ] No auth header
