# Meal delivery wallet charge (frontend)

## What changed

Delivery wallet debits now use the **published lunch/dinner slot final price**, not the constant package average `per_meal_price_snapshot`.

Lunch and dinner on the same day can charge **different** amounts.

## Integration steps

1. After menu **publish**, admin schedule assignments include `final_meal_price` per slot (null while draft).
2. On mark delivered success, read `payment_status` (`charged`) and `charged_amount`.
3. Do **not** assume every delivery debit equals `order.per_meal_price_snapshot`.
4. Wallet history `meal_payment` includes `meal_period`, `service_date`, and `final_meal_price` — use those for labels.
5. Cache keys for menus must include `meal_public_id` + `year` + `month` so publishing one package cannot clear another package’s UI state.

## Mark delivered

```http
POST /api/v1/web/orders/{order_public_id}/deliveries/{delivery_public_id}/mark
Authorization: Token <admin>
Content-Type: application/json

{ "status": "delivered" }
```

Success includes:

```json
{
  "status": "delivered",
  "payment_status": "charged",
  "charged_amount": "62.00",
  "meal_period": "lunch",
  "service_date": "2026-08-05"
}
```

### Errors to handle

| HTTP | `error_code` | UI |
|------|--------------|-----|
| 422 | `MEAL_SLOT_PRICE_MISSING` | Menu not published / slot price missing for that date+period |
| 422 | `WALLET_INSUFFICIENT_FOR_MEAL` | Ask customer to top up |
| 422 | `WALLET_FROZEN` | Wallet frozen |
| 403 | — | Not admin |

## Wallet history

Payment rows may show different amounts for lunch vs dinner. Prefer:

- `amount` (ledger)
- `meal_payment.meal_period`
- `meal_payment.service_date`
- `meal_payment.final_meal_price`

## Average vs final price

| Field | Meaning |
|-------|---------|
| `per_meal_rate` / `per_meal_price_snapshot` | Estimated **average** package rate |
| Slot `final_meal_price` / delivery `charged_amount` | **Actual** charge for that meal |

Public offering may include `per_meal_rate_role: "estimate"`.

## Target clients

Web admin (mark delivery, menu publish) and customer wallet history. Mobile mark-delivery if used must follow the same charge fields.
