# Frontend — Announcements (Admin)

Backend overview: [`../backend/overview.md`](../backend/overview.md).

Public visitor feed (no auth): [`announcements-public.md`](announcements-public.md).

## What to build

1. **Announcements list** — paginated admin table with filters (`is_published`, `type`, `severity`, search).
2. **Create / edit form** — title, description, type, severity, optional banner image, CTA text/URL, schedule, priority, publish toggle.
3. **Publish workflow** — save as draft, then patch to publish; confirm it appears on `/announcements/active/`.
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
| List | GET | `/announcements/?is_published=true&type=offer` |
| Search | GET | `/announcements/?search=summer` |
| Create (JSON) | POST | `/announcements/` |
| Create (with image) | POST multipart | `/announcements/` |
| Detail | GET | `/announcements/{public_id}/` |
| Update / publish | PATCH | `/announcements/{public_id}/` |
| Delete | DELETE | `/announcements/{public_id}/` |

Lists are paginated (`page`, optional `page_size`, default **50**, max **200**).

Ordering: `ordering=-priority` or `ordering=-updated_at` (allowlisted:
`priority`, `publish_at`, `created_at`, `updated_at`).

| Concern | Admin | Public |
|---------|-------|--------|
| Path | `/announcements/` | `/announcements/active/` |
| Auth | Token + verified admin | None |
| Payload | Includes `is_published`, `lifecycle_status`, timestamps | Lean visitor fields |
| Rows | All (drafts, expired, …) | Currently active only |

## Field meanings

| Field | Meaning |
|-------|---------|
| `public_id` | Stable API id (UUID) |
| `title` | Required |
| `description` | Optional body |
| `type` | `notice` \| `offer` \| `new_package` \| `maintenance` \| `announcement` |
| `severity` | `info` \| `warning` \| `success` \| `error` |
| `image` | Absolute URL or `null` |
| `button_text` | Optional CTA label |
| `button_url` | Optional CTA URL (required if `button_text` set) |
| `is_published` | `false` = draft |
| `publish_at` / `publish_until` | UTC ISO-8601 or `null` (`publish_until` inclusive) |
| `priority` | Higher first on public feed |
| `lifecycle_status` | Read-only: `draft` \| `scheduled` \| `active` \| `expired` |

## Publish → public feed workflow

1. `POST /announcements/` with `is_published: false` → draft.
2. Confirm `GET /announcements/active/` does **not** include it.
3. `PATCH /announcements/{public_id}/` with `{"is_published": true}`.
4. Confirm `GET /announcements/active/` returns it (no auth).
5. To hide early: `PATCH` `{"is_published": false}`.

## Request / response examples

### Create draft (JSON)

`POST /announcements/`

```json
{
  "title": "Summer Offer",
  "description": "Get 10% off your next subscription.",
  "type": "offer",
  "severity": "success",
  "button_text": "Order Now",
  "button_url": "https://befood.example/order",
  "is_published": false,
  "publish_at": null,
  "publish_until": null,
  "priority": 10
}
```

`201 Created` (excerpt):

```json
{
  "public_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Summer Offer",
  "type": "offer",
  "severity": "success",
  "image": null,
  "is_published": false,
  "lifecycle_status": "draft",
  "priority": 10
}
```

### Create with banner (multipart)

```http
POST /announcements/
Authorization: Token <admin_token>
Content-Type: multipart/form-data
```

Form fields: `title`, `type`, `severity`, `is_published`, `priority`, `image` (file), optional `description`, `button_text`, `button_url`, schedule fields.

Allowed image types: jpg, jpeg, png, webp. Max size: 5MB.

### Publish

`PATCH /announcements/{public_id}/`

```json
{
  "is_published": true
}
```

### Validation errors

- Blank title → `400` on `title`
- `button_text` without `button_url` → `400` on `button_url`
- `publish_until` not after `publish_at` → `400` on `publish_until`

## Integration checklist

- [ ] Token auth on all admin announcement calls
- [ ] List filters: published, type, severity, search
- [ ] Show `lifecycle_status` in the admin table
- [ ] Multipart image upload on create/edit
- [ ] Draft → publish → verify public `/announcements/active/`
- [ ] Prefer unpublish over delete for temporary hide
