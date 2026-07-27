# Frontend — Site Notices (Admin)

Backend overview: [`../backend/overview.md`](../backend/overview.md).

Public visitor feed (no auth): [`site-notices.md`](site-notices.md).

## What to build

1. **Notices list** — paginated admin table with filters (`is_published`, `severity`, search).
2. **Create / edit form** — bilingual titles/bodies, severity, schedule window, sort order, publish toggle.
3. **Publish workflow** — save as draft (`is_published=false`), then patch to publish; confirm it appears on the public site feed.
4. **Delete / unpublish** — prefer unpublish for temporary hide; delete for permanent removal.

## Auth

```http
Authorization: Token <admin_token>
```

Verified admin only (`IsVerifiedAdmin`). Target client: **web** management UI.

Anonymous and non-admin callers receive `401` / `403`.

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| List notices | GET | `/notices/?is_published=true&severity=warning` |
| Search | GET | `/notices/?search=holiday` |
| Create | POST | `/notices/` |
| Detail | GET | `/notices/{public_id}/` |
| Update / publish | PATCH | `/notices/{public_id}/` |
| Delete | DELETE | `/notices/{public_id}/` |

Lists are paginated (`page`, optional `page_size`, default **50**, max **200**).

Ordering query: `ordering=sort_order` or `ordering=-updated_at` (allowlisted:
`sort_order`, `publish_at`, `created_at`, `updated_at`).

Do **not** confuse with the public feed:

| Concern | Admin | Public |
|---------|-------|--------|
| Path | `/notices/` | `/notices/active/` |
| Auth | Token + verified admin | None |
| Payload | Includes `is_published`, `lifecycle_status`, timestamps | Lean visitor fields only |
| Rows | All notices (drafts, expired, …) | Currently active only |

## Field meanings

| Field | Meaning |
|-------|---------|
| `public_id` | Stable API id (UUID) |
| `title_en` / `title_bn` | Titles; **at least one** required |
| `body_en` / `body_bn` | Plain-text bodies (optional) |
| `severity` | `info` \| `warning` \| `critical` |
| `is_published` | `false` = draft (hidden from public feed) |
| `publish_at` | Optional start (UTC ISO-8601) or `null` |
| `publish_until` | Optional end (UTC ISO-8601) or `null` |
| `sort_order` | Lower appears first on the public feed |
| `lifecycle_status` | Read-only: `draft` \| `scheduled` \| `active` \| `expired` |
| `created_at` / `updated_at` | Timestamps (UTC) |

## Publish → public feed workflow

1. `POST /notices/` with `is_published: false` → draft (`lifecycle_status: "draft"`).
2. Confirm `GET /notices/active/` does **not** include it.
3. `PATCH /notices/{public_id}/` with `{"is_published": true}` (and an open schedule window).
4. Confirm `GET /notices/active/` returns the notice for visitors (no auth).
5. To hide early without deleting: `PATCH` `{"is_published": false}`.

## Request / response examples

### Create draft

`POST /notices/`

```json
{
  "title_en": "Holiday hours",
  "title_bn": "ছুটির সময়সূচি",
  "body_en": "We are closed on Friday.",
  "body_bn": "শুক্রবার আমরা বন্ধ থাকব।",
  "severity": "warning",
  "is_published": false,
  "publish_at": null,
  "publish_until": null,
  "sort_order": 0
}
```

`201 Created` (excerpt):

```json
{
  "public_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title_en": "Holiday hours",
  "title_bn": "ছুটির সময়সূচি",
  "severity": "warning",
  "is_published": false,
  "lifecycle_status": "draft",
  "sort_order": 0,
  "created_at": "2026-07-27T01:00:00Z",
  "updated_at": "2026-07-27T01:00:00Z"
}
```

### Publish

`PATCH /notices/{public_id}/`

```json
{
  "is_published": true
}
```

Response includes `"lifecycle_status": "active"` when the schedule window includes now.

### Validation errors

Empty dual titles → `400` with field errors on `title_en` / `title_bn`.

`publish_until` not after `publish_at` → `400` on `publish_until`.

## Integration checklist

- [ ] Token auth on all admin notice calls
- [ ] List filters: published, severity, search
- [ ] Show `lifecycle_status` in the admin table
- [ ] Draft → publish → verify public `/notices/active/`
- [ ] Prefer unpublish over delete for temporary hide
- [ ] Keep public site integration on `/notices/active/` (no admin token)
