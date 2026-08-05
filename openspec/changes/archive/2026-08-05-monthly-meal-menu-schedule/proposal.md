## Why

Meal cycle planning already locks **how many times** each ingredient is served in a month, but cooks and admins still cannot say **which date and which meal period (lunch/dinner)** those servings land on. Without a day-level schedule, kitchen prep is ad hoc, cross-package cooking cannot be aligned for cost, and customers have no trustworthy “today’s menu” tied to their purchased package. Now that cycle costing exists, the next operational layer is a monthly menu schedule bound to those quotas.

## What Changes

- Add an **admin-only monthly menu schedule** per meal package per cycle month, built on top of a **finalized** `MealCyclePlan` (quotas become hard caps).
- Let admins assign ingredients to concrete **date + meal period** slots (`lunch` | `dinner`) for the full calendar month.
- Enforce quota rules: scheduled count for an ingredient **cannot exceed** that plan line’s `servings_count`; mains should fill slots consistently with cycle `total_meals`.
- Add **cross-package sync / suggestions** so when multiple packages share a cycle month, the kitchen can keep the same (or closest) mains/sides on the same date+period for cooking-cost optimization, even when quotas differ (e.g. chicken 12 vs 10), and keep **lunch/dinner balance** sensible.
- Add **admin-configurable reveal times** (defaults: lunch after 08:00, dinner after 16:00, business timezone) controlling when today’s menu becomes visible.
- Add a **customer “today’s menu” API** for authenticated users with an **active purchased order** for that meal package; full-month schedule stays private (admin/kitchen only).
- Ship beginner-friendly backend documentation for the new workflow.

No **BREAKING** change to existing cycle costing or public meal list/detail contracts in this change (today’s menu is a new endpoint; cycle finalize/reopen semantics stay).

## Capabilities

### New Capabilities

- `monthly-menu-schedule`: Admin month calendar of date + lunch/dinner assignments bound to a finalized cycle plan, with quota validation, draft/publish lifecycle, and kitchen-oriented reads.
- `cross-package-menu-sync`: Suggest and optionally apply best-effort ingredient alignment across packages in the same cycle, respecting per-package quotas and lunch/dinner balance.
- `menu-reveal-settings`: Admin-managed clock windows (and timezone) that control when lunch vs dinner become eligible for customer “today” responses.
- `customer-today-menu`: Authenticated customer endpoint that returns only today’s visible meal period(s) for packages the customer currently has an active order for.

### Modified Capabilities

- `meal-cycle-planning`: Require a finalized plan before a monthly menu schedule can be created/published for that package+month; clarify that reopen of a cycle plan must block or invalidate schedule edits that would break quota integrity.

## Impact

- **App:** `meals/` (new models, services, admin APIs, customer today-menu API, docs under `meals/docs/backend/`).
- **Related:** `orders/` read-only eligibility checks (active order covering today for a `MealCategory`); `user_management` admin permission (`IsVerifiedAdmin`) and customer auth.
- **Depends on:** existing `MealCycle` / `MealCyclePlan` / `MealCyclePlanLine` / `Ingredient` / finalize rules.
- **Clients:** admin web (full month editor + sync UX + reveal settings); customer mobile/web (today’s menu only).
- **Non-goals for this change:** inventory/PO, auto-changing cycle `servings_count` from the schedule, public browsing of future days’ menus, multi-branch kitchen boards.
