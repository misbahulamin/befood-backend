# Frontend — Public FAQ Page

Backend overview: [`../backend/faq-system.md`](../backend/faq-system.md).

Admin management: [`faq-admin.md`](faq-admin.md).

## What to build

1. On FAQ page load, call the public catalog once.
2. Render each type as a **section** heading.
3. Render nested questions as accordion / Q&A items under that section.
4. If the list is empty → show a friendly empty state (“FAQs coming soon”).

Target client: **web** (marketing / public site).

## Auth

**None.** Do not send `Authorization`.

```http
GET /faqs/public/
```

## Success response example

```json
[
  {
    "public_id": "11111111-1111-1111-1111-111111111111",
    "name": "How It Works",
    "sort_order": 0,
    "questions": [
      {
        "public_id": "22222222-2222-2222-2222-222222222222",
        "question": "How do I place an order?",
        "answer": "Pick a meal package, choose dates, and checkout.",
        "sort_order": 0
      }
    ]
  },
  {
    "public_id": "33333333-3333-3333-3333-333333333333",
    "name": "Pricing & Flexibility",
    "sort_order": 1,
    "questions": [
      {
        "public_id": "44444444-4444-4444-4444-444444444444",
        "question": "Can I pause?",
        "answer": "Yes — pause from your account.",
        "sort_order": 0
      }
    ]
  }
]
```

Response is a **JSON array** (not paginated). Types with no published questions are omitted. Unpublished questions never appear. Integer database `id` is not exposed.

## Rendering guidance

| API field | UI |
|-----------|-----|
| `name` | Section title |
| `questions[].question` | Accordion header / question text |
| `questions[].answer` | Expanded answer body |
| `sort_order` | Trust API order; do not re-sort unless product requires it |
| `public_id` | Optional React keys / analytics ids |

## Empty / edge states

| Case | Behavior |
|------|----------|
| `[]` empty array | Empty state UI |
| Type only has drafts | Type omitted entirely |
| Inactive type | Omitted even if it has published questions |

## Errors

Unauthenticated `GET` should normally return `200`. Treat network / 5xx as a retry or soft error banner — do not require login.
