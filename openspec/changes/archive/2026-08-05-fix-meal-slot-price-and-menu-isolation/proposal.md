## Why

Delivery wallet charges currently debit `Order.per_meal_price_snapshot`, which is the package **average** per-meal rate (`total_price ÷ expected servings`), not the actual lunch/dinner selling price for that day’s menu. Separately, package+month menu isolation and finalized-price immutability need hardening so publishing or editing one package’s menu cannot affect another, and ingredient price changes cannot rewrite historical finalized slot prices.

## What Changes

- **BREAKING (payment amount):** On mark-delivered, charge the **delivered slot’s final meal selling price** (ingredient cost + per-meal operational cost + profit for that slot’s assigned ingredients), not the order’s average `per_meal_price_snapshot`.
- Persist an immutable **per-slot final price snapshot** (and supporting cost breakdown) on each `MonthlyMenuSlot` when the monthly menu is published (or when assignments are locked for charging), computed with the same formula as admin one-meal cost preview.
- Keep package-level `per_meal_rate` / `Order.per_meal_price_snapshot` as **reference / eligibility estimate only** — never as the delivery debit amount when a slot snapshot exists.
- Enforce and regression-test **package × month menu isolation**: publish/update/delete/sync of one package schedule MUST NOT mutate another package’s schedule for the same month.
- Make finalized/published menu slot prices **immutable** against live ingredient price/delete/update; later catalog changes affect only draft recalculation and future (re)publish after explicit reopen/unpublish flows.
- Audit remaining average-rate usages (order eligibility min balance, public offering display, wallet docs) and document which remain average-by-design vs must switch to slot price.
- Update backend + frontend docs for new charge amount source and any API fields (`final_meal_price` on slots, delivery payment metadata).

## Capabilities

### New Capabilities

- `meal-slot-final-price`: Per lunch/dinner slot final selling price calculation, snapshot storage, immutability after publish, and use as the delivery charge source of truth.
- `monthly-menu-package-isolation`: Guarantees that each meal package × calendar month menu schedule is independent; publish/edit/sync of one package never deletes, hides, or overwrites another package’s menu.

### Modified Capabilities

- `meal-cycle-costing`: Clarify that package `per_meal_rate` is an estimated/reference average; the one-meal final price formula is the authoritative per-serving charge basis when applied to a concrete slot’s ingredients.
- `customer-meal-package-menu`: Optionally expose published slot `final_meal_price` (read-only) so customers/admins can see the chargeable amount per lunch/dinner without implying average rate.
- `customer-wallet`: Meal-payment history remains delivery-scoped; charged amount MUST reflect the slot final price (and metadata MAY include that price / period context already present).

## Impact

- **Orders:** `orders/services/meal_payment.py`, delivery mark flow, tests (`test_meal_delivery_wallet_payment`, full order process), docs under `orders/docs/`.
- **Meals:** `MonthlyMenuSlot` (new snapshot fields + migration), `menu_schedule.py` publish path, `cycle_calculations.build_one_meal_price_preview` reuse, menu sync isolation, reopen/delete guards, tests for multi-package same month.
- **Wallet:** Transaction amount semantics / docs; possible metadata enrichment.
- **Eligibility:** Review whether wallet min-balance at order create should stay average-based or use max/sum of published slot prices for the ordered month (decision in design).
- **Frontend:** Admin menu UI show per-slot final price; delivery/wallet UIs must not assume constant `per_meal_price_snapshot` equals every debit; package menu screens must key by `meal_public_id` + year/month so one publish cannot clear another package’s client cache.
