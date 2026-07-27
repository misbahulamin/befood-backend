## Why

BeFood’s public website needs a CMS-style FAQ page where visitors see categorized Q&A (e.g. How It Works, Pricing & Flexibility, Freshness & Delivery). Verified admins must manage FAQ **types** and the **questions/answers** under each type from the frontend admin app, including draft vs published visibility — without redeploying the site for copy changes.

## What Changes

- Create a new Django app `faqs` that owns FAQ types (categories) and FAQ entries (question + answer).
- Verified admins can create, list, update, and delete FAQ types (e.g. “How It Works”, “Pricing & Flexibility”).
- Verified admins can create, list, update, and delete FAQ questions under a type; each question MUST belong to exactly one type.
- Each question supports `is_published` so drafts stay off the public FAQ page until published.
- Types and questions support `sort_order` for stable frontend display ordering.
- Expose verified-admin REST CRUD for types and questions (frontend admin app only).
- Expose a **public, unauthenticated** read API that returns FAQ types together with nested questions, including **only** `is_published=true` questions.
- Ship backend and frontend documentation for admin and public contracts.

## Capabilities

### New Capabilities

- `faq-type-management`: Verified-admin REST CRUD for FAQ types (name, slug/order, active lifecycle) used to group questions on the FAQ page.
- `faq-question-management`: Verified-admin REST CRUD for FAQ entries (question, answer, type association, `is_published`, sort order); questions MUST reference an existing type.
- `public-faq-feed`: Unauthenticated public API that returns FAQ types with nested published questions only, ordered for website display.

### Modified Capabilities

- (none)

## Impact

- **New app:** `faqs` registered in `INSTALLED_APPS`; URLs mounted from `core/urls.py` (e.g. `/faqs/`).
- **Models / migrations:** `FaqType` and `FaqQuestion` with `PublicIdMixin`, FK from question → type, `is_published` on questions, `sort_order` on both.
- **APIs:** Admin ViewSets gated by `IsVerifiedAdmin`; public list/feed with `AllowAny` returning nested types + published questions.
- **Permissions:** Reuse `user_management.api.permissions.IsVerifiedAdmin` (same pattern as notices, announcements, assets).
- **Docs:** `faqs/docs/backend/` and `faqs/docs/frontend/` describing admin CRUD and public nested feed.
- **Out of scope:** bilingual fields (can add later), rich HTML CMS, per-user FAQs, search analytics, mobile-operator endpoints, scheduling windows (`publish_at` / `publish_until`).
