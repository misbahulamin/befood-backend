# Guest Meal Orders (Frontend)

Customer flow for prepaid guest meals. Always call **usage → preview → create**. Never trust client-side prices or remaining quota as the source of truth.

## Endpoints

Base: `/api/v1/guest-meals/`  
Auth: verified customer token.

| Step | Method | Path |
|------|--------|------|
| 1. Usage | `GET` | `/api/v1/guest-meals/usage/` |
| 2. Preview | `POST` | `/api/v1/guest-meals/preview/` |
| 3. Create | `POST` | `/api/v1/guest-meals/` |
| List | `GET` | `/api/v1/guest-meals/` |
| Detail | `GET` | `/api/v1/guest-meals/{public_id}/` |

Admin box price / monthly limit: `GET/PATCH /api/v1/web/orders/order-wallet-settings/`  
Fields: `guest_meal_box_price`, `guest_meal_monthly_limit`.

## Recommended client sequence

1. **Gate UI** on active subscription (same as meal home). If usage `remaining_quantity` is `0`, disable order CTA.
2. **Collect** `date`, `meal_period` (`lunch` \| `dinner`), `quantity` (integer ≥ 1).
3. **Preview** before confirm sheet:

```http
POST /api/v1/guest-meals/preview/
Content-Type: application/json

{ "date": "2026-09-30", "meal_period": "lunch", "quantity": 2 }
```

Show server `unit_price`, `total_price`, `monthly_remaining_after_order`, and `recharge_balance_after`. If `422`, surface `detail` / `error_code`.

4. **Create** with a fresh `Idempotency-Key` per user attempt (UUID). Retry the **same** key on network failure; never reuse a key for a different date/period/qty.

```http
POST /api/v1/guest-meals/
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7
Content-Type: application/json

{ "date": "2026-09-30", "meal_period": "lunch", "quantity": 2 }
```

- First success → `201`
- Idempotent replay → `200` with `idempotent_replay: true`
- Conflicting key → `409`

5. **Refresh usage** after success.

## Do not

- Send prices, wallet balances, or subscription ids in the body.
- Treat preview as a reservation (cutoff can pass between preview and create).
- Hardcode box price `10` or meal prices in the app — read from preview/settings.

## Rider / kitchen surfaces

- Deliveryman today-board customer rows include `guest_quantity` (additive to `meal_quantity`).
- Kitchen demand expected/cooking counts already include guest units; no separate kitchen create UI.

## Related docs

- Backend: [guest-meal-order.md](../backend/guest-meal-order.md)
- Wallet thresholds: [wallet-balance-thresholds.md](./wallet-balance-thresholds.md)
