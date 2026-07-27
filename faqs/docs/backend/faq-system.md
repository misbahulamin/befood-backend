# Backend — FAQ System

## Quick summary

Verified admins manage FAQ **types** (sections) and **questions** (Q&A under a type). The public website loads one nested catalog of active types with published questions only.

| Audience | Method | Path | Auth |
|----------|--------|------|------|
| Public FAQ page | `GET` | `/faqs/public/` | None |
| Admin types | `GET\|POST` | `/faqs/types/` | Token + verified admin |
| Admin type detail | `GET\|PATCH\|DELETE` | `/faqs/types/{public_id}/` | Token + verified admin |
| Admin questions | `GET\|POST` | `/faqs/questions/` | Token + verified admin |
| Admin question detail | `GET\|PATCH\|DELETE` | `/faqs/questions/{public_id}/` | Token + verified admin |

## Permissions

| Actor | Admin CRUD | Public feed |
|-------|------------|-------------|
| Anonymous | 401 | Allowed |
| Customer / non-admin | 403 | Allowed |
| Unverified admin | 403 | Allowed |
| Verified admin (`IsVerifiedAdmin`) | Allowed | Allowed |

## Models

### `FaqType`

| Field | Notes |
|-------|--------|
| `public_id` | UUID, API identity |
| `name` | Required, unique (case-insensitive at API layer) |
| `sort_order` | Lower first (default `0`) |
| `is_active` | Inactive types never appear on public feed (default `true`) |

### `FaqQuestion`

| Field | Notes |
|-------|--------|
| `public_id` | UUID, API identity |
| `type` | FK → `FaqType`, `on_delete=PROTECT` |
| `question` / `answer` | Required non-blank text |
| `is_published` | Default `false` (draft) |
| `sort_order` | Lower first within type (default `0`) |

## Publish rules (public feed)

A type appears on `GET /faqs/public/` only when:

1. `is_active=true`
2. It has **at least one** question with `is_published=true`

Nested `questions` include **only** published rows. Drafts never leak.

## Delete guard

`DELETE /faqs/types/{public_id}/` returns **409 Conflict** when the type still has questions. Delete or move questions first. Empty types may be deleted (`204`).

## Ordering

Types and nested questions: `sort_order` ascending, then `created_at`, then `id`.

## How to verify

```bash
python manage.py test faqs.tests.test_faqs
```

Swagger: `/api/docs/` — tags **Public FAQs**, **Admin FAQ Types**, **Admin FAQ Questions**.
