# Instant Meal Offering (Frontend)

Instant Meals show **published** monthly package lunch/dinner slots as one-off browse cards for non-subscribers.

**Instant order / checkout is not available yet.** Render cards and optional CTA stub only.

---

## Endpoint grid

| Method | Path | Auth | Who |
|--------|------|------|-----|
| `GET` | `/meals/instant-meals/` | None | Public Instant section |
| `GET` | `/meals/instant-meal-settings/` | `Token` verified admin | Admin settings screen |
| `PATCH` | `/meals/instant-meal-settings/` | `Token` verified admin | Save profit / duration |

Headers for admin:

```http
Authorization: Token <admin_token>
Content-Type: application/json
```

Optional: `X-Client-Type: web` or `mobile`.

---

## Customer / marketing flow

1. Call `GET /meals/instant-meals/` (optionally `?page=1&page_size=20`).
2. Render each `results[]` item as one card.
3. Sort is already oldest upcoming first — do not re-sort unless product asks.
4. If `subscriber_price` is non-null, show **frontend-owned** static upsell copy, e.g.  
   “Monthly subscriber হলে এই meal মাত্র {subscriber_price} TK তে পাবেন।”  
   Backend does **not** send `subscription_message`.
5. Do **not** call Instant order APIs (none exist).

---

## Admin settings UI flow

1. `GET /meals/instant-meal-settings/` → fill form.
2. Duration control: **predefined options only** (no free date picker):

| UI label | `duration_days` |
|----------|-----------------|
| Today | `1` |
| 3 Days | `3` |
| 7 Days | `7` |
| 15 Days | `15` |
| 25 Days | `25` |
| 30 Days | `30` |

3. Profit: decimal percent (default `50.00`).
4. `PATCH` with changed fields only.
5. Invalid duration (e.g. `10`) → show field error from `duration_days`.

---

## List response shape

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee:2026-08-28:lunch",
      "name": "Chicken + Rice + Dal",
      "meal_period": "lunch",
      "meal_type": "lunch",
      "service_date": "2026-08-28",
      "package_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "package_source": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "package_name": "Student Package",
      "price": "70.00",
      "ingredient_cost": "40.00",
      "operational_cost": "10.00",
      "profit_percent": "50.00",
      "image": "http://localhost:8000/media/meals/...",
      "subscriber_price": "54.00",
      "ingredients": [
        {"name": "Chicken", "product_role": "main"},
        {"name": "Rice", "product_role": "staple"},
        {"name": "Dal", "product_role": "side"}
      ]
    }
  ]
}
```

### Card field meanings

| Field | UI use |
|-------|--------|
| `public_id` | React key / stable id (composite string, not a DB UUID row) |
| `name` | Card title (ingredient names joined with ` + `) |
| `meal_period` / `meal_type` | Lunch/Dinner badge (`lunch` \| `dinner`) |
| `service_date` | Date label (`YYYY-MM-DD`) |
| `package_name` | Package chip (Student / Regular / Premium, …) |
| `package_public_id` | Link to package detail if needed |
| `price` | Instant selling price to display |
| `ingredient_cost` | Optional cost breakdown |
| `operational_cost` | Optional cost breakdown |
| `profit_percent` | Optional admin/debug |
| `image` | Thumbnail (package image; may be null) |
| `subscriber_price` | Value only for upsell static text; may be null |
| `ingredients` | Optional detail list |

---

## Settings response / request

```json
{
  "profit_percent": "50.00",
  "duration_days": 7,
  "updated_at": "2026-08-28T12:00:00.000000Z"
}
```

`PATCH` example:

```json
{ "profit_percent": "70.00", "duration_days": 15 }
```

---

## Edge cases

| Situation | UI |
|-----------|-----|
| Empty `results` | Empty state (“No Instant Meals in the current window”) |
| `image` null | Placeholder art |
| `subscriber_price` null | Hide upsell line |
| Past meals | Never returned by API |
| Same day lunch + dinner | Two cards |
| Same day Student + Regular lunch | Two cards |

---

## Related docs

- Backend: `meals/docs/backend/instant-meal-offering.md`
- Public package menu (subscription marketing): `meals/docs/frontend/public-monthly-package-menu.md`
