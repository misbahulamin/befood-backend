## Context

Kitchen cooking surfaces already treat low-balance meal-stop as “do not cook”:

- `GET /orders/kitchen/today-meal-requirement/` and `GET /orders/kitchen/today-order-details/` omit customers with `CustomerProfile.meal_service_blocked_low_balance=true` from final cooking counts and customer lists (`orders.services.meal_demand._low_balance_blocked_q`).
- Auto meal delivery also excludes the same flag before charging/delivering (`orders.services.auto_meal_delivery`).

The deliveryman today-board (`delivery_zones.services.board.build_deliveryman_board` → `zone_scoped_deliveries`) only filters by zone, active location, live delivery, service date, active meal period, and status (`scheduled` / optional `delivered`). It does **not** exclude meal-stop blocked customers. Those customers often still have lunch/dinner preference on and a `scheduled` `OrderDelivery` row, so riders see them even though kitchen never cooked.

Stakeholders: Delivery Man mobile app, kitchen ops (source of truth for who gets food), wallet threshold automation (sets/clears the block flag).

## Goals / Non-Goals

**Goals:**

- Deliveryman today-board lists only customers who are cooking-eligible for that slot: not low-balance meal-stop blocked.
- Use the same block **flag** kitchen uses (not a live `Wallet.balance < meal_stop_threshold` recompute).
- Keep response contract fields unchanged; only membership / counts change.
- Document the rule for frontend deliveryman integration.

**Non-Goals:**

- Changing kitchen APIs, meal-demand formulas, or wallet threshold cron.
- Turning off lunch/dinner preferences when meal-stop applies.
- Showing wallet balance or meal-stop reason on deliveryman payloads.
- Changing admin zone ops boards unless they share this exact deliveryman board helper (admin ops stay out of scope unless already identical).
- Blocking mark-delivery by meal-stop flag beyond board visibility (auto-delivery already skips; opportunistic mark of a known `public_id` is rare and remains zone-scoped).

## Decisions

1. **Exclude via `meal_service_blocked_low_balance` on queryset**
   - **Choice:** In `zone_scoped_deliveries` (or immediately in `build_deliveryman_board` before listing), `.exclude()` the same Q as kitchen:
     `subscription__customer__meal_service_blocked_low_balance=True OR order__customer__meal_service_blocked_low_balance=True`.
   - **Rationale:** Matches kitchen + auto-delivery; flag is the operational truth after cron / post-debit evaluation. Live balance recompute would diverge from kitchen mid-day.
   - **Alternatives considered:** Filter only in the view serializer loop — rejected (wastes query work, easy to miss on other callers of `zone_scoped_deliveries`). Live wallet threshold check — rejected (kitchen docs explicitly forbid that for cook exclusion).

2. **Reuse shared Q helper when practical**
   - **Choice:** Prefer importing/reusing `_low_balance_blocked_q` from `orders.services.meal_demand` **or** extract a tiny shared helper (e.g. under `orders.services.wallet_balance_thresholds` / subscription parent) if importing a private `_` function is undesirable.
   - **Rationale:** One definition of “blocked for cooking/delivery ops.”
   - **Alternatives considered:** Duplicate the Q inline in `board.py` — acceptable short-term but higher drift risk.

3. **Apply to all callers of `zone_scoped_deliveries` used for rider delivery lists**
   - **Choice:** Put the exclude on `zone_scoped_deliveries` so any future rider list built from that helper inherits eligibility.
   - **Rationale:** Single choke point for zone delivery listing.
   - **Note:** If admin zone ops later needs “include blocked for diagnostics,” add an explicit `include_low_balance_blocked=False` kwarg defaulting to False for deliveryman.

4. **Docs + tests as the acceptance gate**
   - **Choice:** One board test with two zone customers (one blocked, one not) asserting only the unblocked row appears and `total_count` matches; update frontend/backend zone delivery docs.
   - **Rationale:** Product bug is visibility mismatch with kitchen; regression test locks the parity rule.

## Risks / Trade-offs

- **[Risk] Block flag lag before cron** → Mitigation: Same as kitchen; post-debit path already sets the flag immediately after a successful meal charge. Board and kitchen stay consistent with each other even if both lag behind raw wallet balance.
- **[Risk] Rider expects “all meal-on” customers** → Mitigation: Document that today-board = cookable deliveries only; meal-on preference alone is insufficient.
- **[Risk] Shared `zone_scoped_deliveries` used for a future “include blocked” admin view** → Mitigation: Optional kwarg to include blocked rows if needed later; default remains exclude.
- **[Trade-off] Mark endpoint not hard-blocked by meal-stop** → Accepted: board omission is the primary fix; charging path already no-ops / skips blocked in auto-delivery; admin can still intervene via admin tools.

## Migration Plan

1. Ship queryset exclude + tests + docs in one deploy (no schema/migration).
2. No client schema change; apps that only render the board list automatically show fewer rows.
3. Rollback: revert the exclude in `board.py` (behavior returns to previous over-inclusive list).

## Open Questions

- None blocking implementation. Optional follow-up: whether admin zone delivery ops list should show blocked customers with a badge (out of scope here).
