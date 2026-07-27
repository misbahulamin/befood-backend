# Frontend — FAQ Admin

Backend overview: [`../backend/faq-system.md`](../backend/faq-system.md).

Public website feed: [`faq-public.md`](faq-public.md).

## What to build

Admin UI to:

1. Create / edit / deactivate FAQ **types** (sections such as “How It Works”).
2. Create / edit / publish FAQ **questions** under a type.
3. Never show drafts on the public FAQ page until `is_published=true`.

Target client: **web admin**.

## Auth

```http
Authorization: Token <admin_token>
```

Caller must be a **verified admin**. Customers and unverified admins receive `403`.

## Recommended workflow

1. `POST /faqs/types/` — create section (`name`, optional `sort_order`).
2. `POST /faqs/questions/` — add Q&A with `type_public_id` (starts unpublished).
3. `PATCH /faqs/questions/{public_id}/` with `{ "is_published": true }` when ready.
4. Confirm on `GET /faqs/public/` (no auth) that the item appears.

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| List types | GET | `/faqs/types/` |
| Create type | POST | `/faqs/types/` |
| Update type | PATCH | `/faqs/types/{public_id}/` |
| Delete type | DELETE | `/faqs/types/{public_id}/` |
| List questions | GET | `/faqs/questions/?type_public_id=&is_published=` |
| Create question | POST | `/faqs/questions/` |
| Publish / edit | PATCH | `/faqs/questions/{public_id}/` |
| Delete question | DELETE | `/faqs/questions/{public_id}/` |

Admin lists are paginated (default `page_size=50`, max `200`).

## Create type example

```http
POST /faqs/types/
Authorization: Token <token>
Content-Type: application/json

{
  "name": "Pricing & Flexibility",
  "sort_order": 1,
  "is_active": true
}
```

```json
{
  "public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Pricing & Flexibility",
  "sort_order": 1,
  "is_active": true,
  "question_count": 0,
  "created_at": "2026-07-27T12:00:00Z",
  "updated_at": "2026-07-27T12:00:00Z"
}
```

## Create question example

```http
POST /faqs/questions/
Authorization: Token <token>
Content-Type: application/json

{
  "type_public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "question": "Can I pause my subscription?",
  "answer": "Yes — pause from your account or contact support.",
  "sort_order": 0,
  "is_published": false
}
```

Omitting `is_published` also stores a draft (`false`).

## Publish example

```http
PATCH /faqs/questions/{public_id}/
Authorization: Token <token>
Content-Type: application/json

{ "is_published": true }
```

## Filters

| Query | Applies to | Meaning |
|-------|------------|---------|
| `is_active` | types | Active / inactive types |
| `search` | types | Name contains |
| `type_public_id` | questions | Only questions under that type |
| `is_published` | questions | Draft vs published |
| `search` | questions | Question/answer contains |

## Edge cases

| Situation | Expected |
|-----------|----------|
| Duplicate type name | `400` on `name` |
| Unknown `type_public_id` | `400` on `type_public_id` |
| Delete type with questions | `409` — delete questions first |
| Delete empty type | `204` |
| Use integer PK in path | `404` — only `public_id` |

## Field meanings

| Field | Meaning |
|-------|---------|
| `public_id` | Stable UUID for links and paths |
| `name` | Section title on FAQ page |
| `sort_order` | Display order (lower first) |
| `is_active` | Soft hide type from public feed |
| `type_public_id` | Parent type UUID |
| `question` / `answer` | Copy shown to visitors when published |
| `is_published` | Admin-only visibility control |
| `question_count` | Admin convenience count of questions under the type |
