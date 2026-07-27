## Context

BeFood’s public website needs a categorized FAQ page. Verified admins already manage similar CMS content via REST (`notices`, `announcements`) using `IsVerifiedAdmin` and `PublicIdMixin`. There is no FAQ domain yet.

This change adds a dedicated `faqs` app: admins create **types** (categories) and **questions** under those types; the public site loads one nested feed of types + published Q&A only.

Stakeholders: verified admins (CRUD), public website (FAQ page), backend maintainers (app boundary).

Constraints: follow Django app layout (`api/`, `services/`, `docs/`); reuse `IsVerifiedAdmin`; mount under top-level `/faqs/` like `/notices/` and `/announcements/`; do not break existing apps.

## Goals / Non-Goals

**Goals:**

- Own FAQ types and questions in app `faqs`.
- Verified-admin REST CRUD for types and for questions (each question under exactly one type).
- Publish/unpublish per question via `is_published`.
- Stable display order via `sort_order` on types and questions.
- One public unauthenticated API that returns types nested with **only published** questions.
- Backend + frontend docs for admin workflow and public FAQ page integration.

**Non-Goals:**

- Bilingual fields (`_en` / `_bn`) in v1 (single-language `name` / `question` / `answer`).
- Schedule windows (`publish_at` / `publish_until`) — publish flag only.
- Rich HTML / media attachments on answers.
- Public write endpoints or customer-submitted FAQs.
- Mobile-operator-specific FAQ routes.
- Soft-delete with restore UI beyond hard delete or simple `is_active` on types if needed for empty-type filtering.

## Decisions

### 1. New app `faqs`

**Why:** FAQ is a distinct CMS surface (typed Q&A catalog), not a notice or announcement.  
**Alternatives considered:** Stuff into `announcements` — rejected (different shape and public UX). Django Admin only — rejected (product wants frontend-admin REST like announcements).

### 2. Data model

```text
FaqType (PublicIdMixin)
  name          CharField (required, unique case-insensitive or unique)
  slug          SlugField optional (auto from name) OR omit and use public_id only
  sort_order    IntegerField default 0  # lower shows first
  is_active     bool default True       # hide empty/retired types from public feed
  created_at, updated_at

FaqQuestion (PublicIdMixin)
  type          FK → FaqType (PROTECT or CASCADE; prefer PROTECT + require reassign/delete questions first)
  question      CharField / TextField (required)
  answer        TextField (required)
  is_published  bool default False
  sort_order    IntegerField default 0  # lower shows first within type
  created_at, updated_at
```

**Ordering (public + admin defaults):** `sort_order` ascending, then `created_at` ascending (or `-created_at` for admin newest-first — prefer ascending for FAQ readability), then `id` tie-breaker.

**Delete rules:** Deleting a type that still has questions MUST be rejected (`409`/`422`) unless product chooses CASCADE; prefer PROTECT so admins delete/move questions first.  
**Alternatives:** CASCADE delete questions with type — simpler but riskier; document if chosen. **Decision: PROTECT** (safer for CMS).

### 3. URL and auth layout

```text
# Public feed (types + nested published questions)
GET               /faqs/public/                    AllowAny (no auth classes)

# Admin FAQ types
GET|POST          /faqs/types/                     IsVerifiedAdmin
GET|PATCH|DELETE  /faqs/types/{public_id}/         IsVerifiedAdmin

# Admin FAQ questions
GET|POST          /faqs/questions/                 IsVerifiedAdmin
GET|PATCH|DELETE  /faqs/questions/{public_id}/     IsVerifiedAdmin
```

Register `public` (and `types` / `questions`) as explicit path prefixes so they are never parsed as a `public_id`.

**Public response shape (conceptual):**

```json
[
  {
    "public_id": "...",
    "name": "How It Works",
    "sort_order": 0,
    "questions": [
      {
        "public_id": "...",
        "question": "...",
        "answer": "...",
        "sort_order": 0
      }
    ]
  }
]
```

Public feed MUST:

1. Include only types with `is_active=true`.
2. Nest only questions with `is_published=true`.
3. Optionally omit types that have zero published questions (recommended for cleaner FAQ UI) — **Decision: omit empty types** on the public feed.
4. Never expose unpublished questions or admin-only fields.

Admin list for questions MAY filter by `type` (`type_public_id`), `is_published`, and search `question`/`answer`. Admin type list MAY include question counts.

### 4. Service layer

- `faqs/services/faq_catalog.py` (or similar):
  - `get_public_faq_catalog()` — queryset/prefetch with published filter + ordering.
  - Optional helpers for create/update validation (unique name, required type FK).
- Views stay thin; business rules in services/serializers.

### 5. Identifiers and serializers

- Expose `public_id` on all API resources; never sequential integer `id` to clients.
- Nested create/update for questions uses `type_public_id` (not integer FK).
- `lookup_field = "public_id"` on admin ViewSets.

### 6. Documentation deliverables

- `faqs/docs/backend/faq-system.md` — models, publish rules, permissions, admin vs public.
- `faqs/docs/frontend/faq-public.md` — public nested feed, no auth, empty states.
- `faqs/docs/frontend/faq-admin.md` — type CRUD then question CRUD workflow, publish flag.

## Risks / Trade-offs

- **[Risk] Empty types clutter public page** → Mitigation: omit types with no published questions on public feed; admin still sees all types.
- **[Risk] Accidental publish of incomplete answers** → Mitigation: default `is_published=false`; admin must explicitly publish.
- **[Risk] Deleting a type orphans UX** → Mitigation: FK `PROTECT` + clear 422/409 error when questions remain.
- **[Trade-off] Single language** → Matches stated v1 need; bilingual can be additive later.
- **[Trade-off] Separate admin list endpoints vs one nested admin payload** → Flat CRUD is simpler for forms; public feed is the only nested read. Acceptable duplication of serializers.

## Migration Plan

1. Add `faqs` app, models, migrations; register in `INSTALLED_APPS` and `core/urls.py`.
2. Deploy migrations; seed optional example types via admin/API (no required data migration).
3. Frontend admin: manage types → add questions → publish.
4. Frontend website: call `/faqs/public/` for the FAQ page.
5. **Rollback:** remove URL include and disable app; reverse migration only if no critical production dependency yet.

## Open Questions

- None blocking: bilingual and schedule windows deferred by proposal.
- Seed default types (How It Works, Pricing, …) vs empty catalog — leave empty; admins create types (optional management command later, not required for v1).
