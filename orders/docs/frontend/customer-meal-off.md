# Frontend: customer meal-off

## Summary

Show a **Meal Off** action on each upcoming delivery while `can_meal_off` is true. After success, the slot is skipped (no meal that lunch/dinner). Deadlines are server-driven; do not hardcode 23:59 / 14:00 in the client beyond display defaults.

**Breaking / new:** delivery objects gain `can_meal_off`, `meal_off_deadline_at`, `skip_source`.

**Identifiers:** use order/delivery UUID `public_id` in paths (not integer ids). See [`order-public-uuid.md`](order-public-uuid.md).

## When to show the button

On order detail / current package, for each delivery:

1. Show **Meal Off** only if `can_meal_off === true`.
2. Optionally show countdown using `meal_off_deadline_at`.
3. Hide after success or when status is not `scheduled`.

## API

```http
POST /orders/{order_public_id}/deliveries/{delivery_public_id}/meal-off
Authorization: Token <customer-token>
Content-Type: application/json

{ "note": "optional" }
```

Success: `200` with updated delivery (`status: skipped`, `skip_source: customer`, `public_id`).

Errors:

| Status | Meaning | UI |
|--------|---------|-----|
| 400 | Deadline passed / bad state | Toast: “Deadline has passed” |
| 404 | Not your order / missing slot | Refresh list |
| 409 | Already skipped/delivered | Refresh delivery |

Trailing slash optional; backend supports no-slash POST.

## Admin settings UI

```http
GET/PATCH /api/v1/web/orders/meal-off-settings/
```

Fields: `timezone`, `lunch_off_time`, `dinner_off_time`.

Label clearly:

- Lunch off time = deadline on the **day before** lunch
- Dinner off time = deadline on the **same day** as dinner

## Edge cases

- Daily lunch package: meal-off the only slot → order becomes `completed`.
- Monthly both: meal-off one lunch does not affect dinner that day.
- No refund messaging: “Meal off cancels cooking for this slot; package price is unchanged.”

## Target clients

- Mobile / web customer: Meal Off on upcoming slots
- Web admin: settings + kitchen board (`skip_source` to see customer vs admin skips)
