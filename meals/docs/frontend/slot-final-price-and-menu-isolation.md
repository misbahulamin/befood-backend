# Frontend instructions — slot final price & menu isolation

## Why

1. Delivery wallet charges use **per lunch/dinner final selling price**, not package average.
2. Each meal package × month menu is independent; publishing one package must not clear another in the UI.

## Do

| Area | Instruction |
|------|-------------|
| Mark delivered | Show `charged_amount` / wallet `amount`; never hard-code `per_meal_price_snapshot` as the debit |
| Admin menu assignments | After publish, show dual pricing from schedule detail: `selected_ingredients_cost`, `subscriber_price` / `final_meal_price`, `subscriber_pricing.profit_amount`, `instant_price`, `instant_pricing.profit_amount`. Draft → nulls. **Render only — no client-side math.** |
| Public offering | Treat `per_meal_rate` as estimate (`per_meal_rate_role: "estimate"`) |
| Wallet history | Render `meal_period` + `service_date` + `amount` (lunch/dinner may differ) |
| Menu cache / state | Key by `meal_public_id` + `year` + `month` (never month alone) |
| Sync apply | Confirm target package before apply; source package stays unchanged |

## Don’t

- Don’t assume every delivery for an order debits the same amount.
- Don’t refetch one package’s menu and overwrite another package’s month cache.
- Don’t treat ingredient catalog price edits as changing already-published slot prices (backend freezes on publish).

## Related docs

- `meals/docs/frontend/published-menu-dual-pricing.md`
- `orders/docs/frontend/meal-delivery-wallet-payment.md`
- `wallet/docs/frontend/customer-wallet.md`
- `meals/docs/backend/monthly-meal-menu-schedule.md`
