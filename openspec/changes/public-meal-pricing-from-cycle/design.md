## Context

BeFood already finalizes month-based cycle plans with snapshots (`snapshot_total_cost`, `snapshot_per_meal_rate`) but does **not** write those onto `MealCategory`. Admins still supply `total_price` at meal create. Public detail is thin (`description` + price only), so customers cannot see the finalized month menu that justifies the package price.

Orders snapshot `meal.total_price` at purchase time, so published price must stay reliable.

Stakeholders: admins (finalize publishes price), customers (public detail for purchase decisions), order flow (needs priced meals).

## Goals / Non-Goals

**Goals:**

- Meal create without mandatory `total_price`.
- Finalize publishes package price onto the linked meal (`total_price = snapshot_total_cost`).
- Public meal detail shows clear, purchase-oriented finalized cycle details (month, meal count, menu servings, package total, per-meal rate).
- Keep admin-only internals (raw kg purchase prices, draft plans) off public responses.
- Guard orders when a meal has no published price yet.

**Non-Goals:**

- Day-by-day calendar UI.
- Auto-creating meals from Excel.
- Changing order period logic.
- Multi-currency.
- Exposing every admin margin note field publicly (optional high-level cost bands only if useful).

## Decisions

### 1. `total_price` becomes nullable until first publish

- Migration: `MealCategory.total_price` → `null=True`, `blank=True`.
- Admin create/update: `total_price` omitted / read-only on write (or ignored if sent).
- `pricing_status`: derived `unpriced` | `priced` (priced when `total_price` is not null).
- Existing seeded meals keep their prices until next finalize overwrites.

**Alternative:** Keep required price with placeholder `0.01`. Rejected — confuses customers and orders.

### 2. Finalize publishes; reopen does not unpublish

```
finalize_plan()
  → validate + snapshot (existing)
  → meal.total_price = plan.snapshot_total_cost
  → meal.save(update_fields=[...])
  → return summary including published meal price
```

- Source field: `snapshot_total_cost` (already includes other cost + profit).
- Public `per_meal_price`: prefer `snapshot_per_meal_rate` from the **current published plan**; fallback to `total_price / present_month_meals` only if no plan linked (legacy).
- Reopen: clear plan status to draft + clear plan snapshots, but **leave** `MealCategory.total_price` as last published value until a new finalize.

**Alternative:** Clear meal price on reopen. Rejected — storefront would go blank while admin edits.

### 3. “Current offering” = latest finalized plan for that meal

Resolver:

```text
MealCyclePlan.objects
  .filter(meal_category=meal, status=finalized)
  .select_related('cycle')
  .order_by('-cycle__year', '-cycle__month', '-finalized_at')
  .first()
```

If none → public detail has `current_cycle_offering: null` and `pricing_status: unpriced` (unless legacy `total_price` still set without a plan — then `priced` with offering null).

When multiple months exist, newest finalized month wins for the meal storefront.

### 4. Public detail payload (customer-safe)

**List (lean):** id, name, thumbnail, meal_type, `total_price`, `per_meal_price`, `pricing_status`, `is_active`.

**Detail (rich, public):** list fields + description + `current_cycle_offering`:

| Field | Why customers need it |
| --- | --- |
| `year`, `month`, `cycle_days`, `total_meals` | Understand package scope |
| `package_total_price` | What they pay for the package |
| `per_meal_rate` | Compare value |
| `menu_items[]` | `name`, `product_role`, `servings_count` | What’s included how often |
| `finalized_at` | Freshness |

**Exclude from public:** ingredient `price_per_kg`, draft plans, admin `notes`, raw margin edit controls.  
**Include optionally:** high-level `product_cost` / `other_cost` / `profit` from snapshots for price transparency — **yes**, include as read-only from snapshots (matches Excel Final Meal Price List trust story).

Default public list filter: active meals; unpriced meals may still appear for browsing but purchase endpoints MUST reject unpriced meals.

### 5. Admin meal APIs

- Create: `meal_name`, `meal_thumbnail`, `meal_type`, `description`, `is_active` — no `total_price`.
- Update: same; do not allow manual overwrite of `total_price` via meal PATCH (price only via finalize). If needed later, add explicit admin override endpoint — out of scope.
- Response may still show `total_price` as read-only.

### 6. Orders guard

When creating an order for a meal with `total_price is null`, return `422`/`400` with clear message: meal pricing not published yet.

## Risks / Trade-offs

- **[Risk] Existing clients send `total_price` on create** → Mitigation: ignore or accept but do not persist as source of truth; document breaking change.
- **[Risk] Unpriced meals visible publicly** → Mitigation: `pricing_status` + order rejection; UI can disable Buy.
- **[Risk] Reopen while customers still see old price** → Mitigation: intentional; re-finalize updates; document admin workflow.
- **[Risk] Two finalized plans different months** → Mitigation: deterministic “latest month” resolver.
- **[Trade-off] Removing old “public APIs hide cycle data” rule** → Replaced by customer-safe offering only.

## Migration Plan

1. Nullable `total_price` migration; backfill unchanged for existing rows.
2. Publish helper in `finalize_plan`; adjust reopen docs/tests.
3. Public serializers + offering builder; update meal create serializer/tests.
4. Order create validation for null price.
5. Docs update in meal-cycle + public meal guide.
6. Rollback: reverse migration only after restoring required price writes (git).

## Open Questions

- Should public list hide unpriced meals by default? **Default: show with `pricing_status=unpriced`; Buy disabled.**
- Prefer current calendar month’s finalized plan over “latest any month” when both exist? **Default: latest finalized by year/month** (simpler, matches “most recent published menu”).
- Expose cost band (`product_cost`/`other`/`profit`) publicly? **Default: yes** from snapshots only.
