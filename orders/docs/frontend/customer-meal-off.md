# Frontend: customer meal-off / meal-on

## Summary

Show **Meal Off** when `can_meal_off` is true, and **Meal On** when `can_meal_on` is true. Both actions share the same `meal_off_deadline_at`. After that deadline, hide both actions — the slot is locked.

**New:** `can_meal_on` on delivery objects; `POST .../meal-on` endpoint.

**Identifiers:** use order/delivery UUID `public_id` in paths (not integer ids). See [`order-public-uuid.md`](order-public-uuid.md).

## When to show buttons

On order detail / current package, for each delivery:

1. Show **Meal Off** only if `can_meal_off === true`.
2. Show **Meal On** only if `can_meal_on === true` (customer-skipped, before deadline).
3. Optionally show countdown using `meal_off_deadline_at` (applies to both).
4. After deadline: both flags false — do not offer Off or On; refresh if needed.

## Default vs off (UI copy)

- No meal-off → customer is expected to receive the meal; billing happens when ops mark delivered.
- Meal-off → no delivery for that slot; no wallet charge for that slot.
- Meal-on before deadline → back to expected meal; still no charge until delivered.

## API

### Meal Off

```http
POST /orders/{order_public_id}/deliveries/{delivery_public_id}/meal-off
Authorization: Token <customer-token>
Content-Type: application/json

{ "note": "optional" }
```

Success: `200` with `status: skipped`, `skip_source: customer`, `can_meal_on: true` (if still before deadline).

### Meal On

```http
POST /orders/{order_public_id}/deliveries/{delivery_public_id}/meal-on
Authorization: Token <customer-token>
Content-Type: application/json

{ "note": "optional" }
```

Success: `200` with `status: scheduled`, `skip_source: null`.

Errors (both):

| Status | Meaning | UI |
|--------|---------|-----|
| 400 | Deadline passed / bad state | Toast: “Deadline has passed” |
| 404 | Not your order / missing slot | Refresh list |
| 409 | Wrong state (already terminal / not customer skip) | Refresh delivery |

Trailing slash optional; backend supports no-slash POST.

## Admin settings UI

```http
GET/PATCH /api/v1/web/orders/meal-off-settings/
```

Fields: `timezone`, `lunch_off_time`, `dinner_off_time`.

Label clearly:

- Lunch off time = deadline on the **day before** lunch (gates Off **and** On)
- Dinner off time = deadline on the **same day** as dinner (gates Off **and** On)

## Edge cases

- Daily lunch package: meal-off the only slot → order becomes `completed`; meal-on before deadline → order reopens (`confirmed` / `active`) and slot is `scheduled` again.
- Monthly both: meal-off one lunch does not affect dinner that day.
- Admin-skipped slots: `can_meal_on` stays false — customer cannot undo admin skip.
- No refund messaging: “Meal off cancels cooking for this slot; package price is unchanged.”

## Target clients

- Mobile / web customer: Meal Off / Meal On on upcoming slots
- Web admin: settings + kitchen board (`skip_source` to see customer vs admin skips)
