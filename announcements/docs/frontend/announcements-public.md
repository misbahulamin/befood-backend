# Frontend — Announcements (Public Popup)

Backend overview: [`../backend/overview.md`](../backend/overview.md).

Admin management UI (Token auth): [`announcements-admin.md`](announcements-admin.md).

## What to build

1. On website load (or layout mount), call the public active feed.
2. If `results` is empty → render nothing.
3. If one or more announcements → show popup/modal in API order (highest `priority` first).
4. Support **image** popups, **text-only** notices, and **CTA** buttons.
5. On close, store the announcement `public_id` in `localStorage` so it is not shown again in the same session (or longer, as product decides).
6. On CTA click, navigate to `button_url` (new tab or same tab per UX).

## Auth

**None.** Do not send `Authorization`. This endpoint is public for all visitors.

Target client: **web** (marketing / public site).

Do **not** confuse with `/notices/active/` (bilingual operational banners without image/CTA).

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| Load active announcements | GET | `/announcements/active/` |
| Paginate | GET | `/announcements/active/?page=2&page_size=20` |

Default `page_size` is **20**; maximum **50**.

## Success response example

```http
GET /announcements/active/
```

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "public_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "title": "Summer Offer",
      "description": "Get 10% off your next subscription.",
      "type": "offer",
      "severity": "success",
      "image": "https://api.example/media/announcements/banners/summer-offer-20260727-120000.jpg",
      "button_text": "Order Now",
      "button_url": "https://befood.example/order",
      "publish_at": "2026-07-27T00:00:00Z",
      "publish_until": "2026-08-01T00:00:00Z",
      "priority": 10
    }
  ]
}
```

## Empty state

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}
```

UI: hide the popup region entirely.

## Field meanings

| Field | Meaning |
|-------|---------|
| `public_id` | Stable id (React `key`; dismiss tracking key) |
| `title` | Popup title |
| `description` | Body text (may be empty) |
| `type` | `notice` \| `offer` \| `new_package` \| `maintenance` \| `announcement` |
| `severity` | `info` \| `warning` \| `success` \| `error` (styling hint) |
| `image` | Absolute image URL or `null` |
| `button_text` | CTA label (empty = no button) |
| `button_url` | CTA href (empty when no CTA) |
| `publish_at` / `publish_until` | Schedule window (informational; already filtered) |
| `priority` | Display precedence (API already sorted high → low) |

Draft / unpublished flags are **not** returned.

## Suggested integration flow

1. `GET /announcements/active/` on mount.
2. Read dismissed ids from `localStorage` (e.g. key `befood_dismissed_announcements`).
3. Filter `results` to exclude dismissed ids.
4. Show the first remaining item as the primary popup (highest priority).
5. Optionally queue the rest (“next” / stack).
6. On dismiss: append `public_id` to the localStorage list.
7. If `button_text` and `button_url` are set → render CTA; click → `window.location` or `window.open`.
8. If `image` is set → render image banner; else text-only layout.

### localStorage example

```js
const KEY = 'befood_dismissed_announcements';

function getDismissed() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]');
  } catch {
    return [];
  }
}

function dismiss(publicId) {
  const ids = new Set(getDismissed());
  ids.add(publicId);
  localStorage.setItem(KEY, JSON.stringify([...ids]));
}
```

Dismiss is **client-only**. The API always returns all currently active announcements.

## Severity / type UI hints

| `severity` | Suggested UI |
|-------------|--------------|
| `info` | Neutral / brand |
| `success` | Positive / offer emphasis |
| `warning` | Amber attention |
| `error` | Strong alert (e.g. maintenance) |

| `type` | Suggested use |
|--------|----------------|
| `offer` | Promo / discount popup |
| `new_package` | Package launch |
| `maintenance` | Downtime notice |
| `notice` / `announcement` | General messaging |

## Why this API

Admins schedule promotional popups from the management UI. The website needs one unauthenticated fetch so every visitor sees the same live promotions without login.

## Integration checklist

- [ ] Fetch on public layout mount
- [ ] Handle empty `results`
- [ ] Respect API order (priority)
- [ ] Image + text-only + CTA variants
- [ ] Dismiss → `localStorage` by `public_id`
- [ ] Use `public_id` as list key
- [ ] No auth header
- [ ] Responsive mobile + desktop modal
