# Admin subscription cancellation (backend)

## Quick summary

Verified admins cancel a customer’s active meal subscription from Customer 360. Customer self-cancel and admin cancel share one canonical service: `orders.services.subscription_service.cancel_subscription`.

Each `SCHEDULED` delivery is classified with `is_past_meal_cutoff` (Asia/Dhaka meal-off settings):

| Condition | Result |
|-----------|--------|
| Business now **strictly after** lunch/dinner deadline | **Preserve** (`scheduled`) — finalized |
| At or before deadline | **Soft-skip** (`skipped` / `system`) |
| Already `delivered` / `skipped` / `missed` | Untouched |

Exact cutoff instant remains cancellable (same as meal-off).

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| `GET` | `/api/v1/web/customers/{public_id}/cancel-subscription-preview/` | `IsVerifiedAdmin` |
| `POST` | `/api/v1/web/customers/{public_id}/cancel-subscription/` | `IsVerifiedAdmin` |

Customer self-cancel (unchanged path, shared semantics):

| Method | Path | Auth |
|--------|------|------|
| `POST` | `/api/v1/subscriptions/current/cancel/` | `IsVerifiedCustomer` |

## Preview / cancel response

```json
{
  "subscription": {
    "public_id": "...",
    "status": "cancelled",
    "cancelled_at": "2026-09-28T11:00:00+06:00",
    "cancel_effective_on": "2026-09-28",
    "cancel_source": "admin",
    "cancelled_by": { "id": 1, "email": "admin@example.com" }
  },
  "cancelled_meals": [
    {
      "public_id": "...",
      "service_date": "2026-09-28",
      "meal_period": "dinner",
      "estimated_charge": "80.00"
    }
  ],
  "preserved_finalized_meals": [
    {
      "public_id": "...",
      "service_date": "2026-09-28",
      "meal_period": "lunch",
      "estimated_charge": "80.00"
    }
  ],
  "wallet": {
    "balance": "300.00",
    "recharge_balance": "300.00",
    "meal_stop_threshold": "100.00",
    "finalized_meal_liability": "80.00",
    "withdrawable_balance": "220.00"
  }
}
```

Preview is read-only: subscription stays `active`; wallet block still shows **post-cancel** figures (`assume_cancelled`).

`POST` body (optional): `{ "reason": "..." }`.

## Liability pricing

`finalized_meal_liability` and each meal’s `estimated_charge` use `estimate_delivery_charge` — the **same** `_resolve_charge_amount` path as `charge_delivered_meal` (published slot `final_meal_price_snapshot`). No cancellation-specific fallback or missing-price special case.

## Audit fields

Additive on `CustomerSubscription`:

- `cancelled_by` (FK to user, nullable)
- `cancel_source` (`customer` | `admin` | `system`, nullable)

Activity feed `subscription_cancelled` refs include `cancel_source` and actor email when present.

## Errors

| Status | When |
|--------|------|
| `401` | Unauthenticated |
| `403` | Non-admin / unverified admin |
| `404` | No active subscription for that customer |

## Related

- Wallet post-cancel withdrawable: `wallet/docs/backend/customer-wallet.md`
- Meal-off cutoffs: `orders/docs/backend/customer-meal-off.md`
- Charge-on-deliver: `orders/docs/backend/meal-delivery-wallet-payment.md`
