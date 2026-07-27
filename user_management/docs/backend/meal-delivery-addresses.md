# Meal delivery addresses (backend)

## Quick summary

Customers maintain a **delivery place book** (Home, Office, …) separate from identity addresses (`present` / `permanent`). They set **usual lunch** and **usual dinner** places, optionally add **weekday overrides**, and the system **resolves + snapshots** the destination onto each `OrderDelivery` slot.

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/user_management/customer/delivery-places/` | List / create places |
| GET/PATCH/DELETE | `/user_management/customer/delivery-places/{public_id}/` | Retrieve / update / delete |
| GET/PUT | `/user_management/customer/delivery-preferences/` | Usual lunch/dinner places |
| GET/PUT | `/user_management/customer/delivery-preferences/day-overrides/` | Replace-set weekday overrides |
| GET | `/user_management/customer/delivery-preferences/preview/?from=&to=` | Resolved destinations for a date range |

Auth: `Authorization: Token <key>` + customer profile (`HasCustomerProfile`).

## Permissions

| Action | Who |
|--------|-----|
| CRUD own places | Authenticated customer (owner only) |
| Preferences / overrides / preview | Authenticated customer (own data) |
| Foreign `public_id` | `404 Not Found` |
| Ops view of destination | Via order delivery serializers / admin (snapshot fields) |

## Key models

- `CustomerDeliveryPlace` — labeled place; soft cap **10** active places per customer
- `MealDeliveryPreference` — 1:1 with profile; `lunch_place`, `dinner_place`
- `MealDeliveryDayOverride` — unique `(customer, meal_period, weekday)` → place; weekday **Monday=0 … Sunday=6**
- `OrderDelivery` snapshot fields — `delivery_label_snapshot`, `delivery_full_address_snapshot`, area/city/lat/lng + nullable `delivery_place` FK (`SET_NULL`)

Identity `CustomerAddress` (`present`/`permanent`) is unchanged. Legacy `is_default_delivery` remains for transition.

## Resolution rules

For `(customer, service_date, meal_period)`:

1. Active day override for that ISO weekday + period  
2. Else preference default for that period (if active)  
3. Else first active place / lazy create from present default delivery address  

Preference/override saves call `resync_future_scheduled_deliveries` for future `scheduled` rows only. `delivered` / `skipped` / `missed` snapshots are never rewritten.

## Business validation

- `label` and `full_address` required on place create  
- Soft cap: max 10 active places  
- Delete blocked with `400` if place is lunch/dinner default or used by an override  
- Place in preferences must belong to the same customer  
- Preview range max 62 days  

## Request / response examples

### Create place

`POST /user_management/customer/delivery-places/`

```json
{
  "label": "Office",
  "full_address": "Floor 5, ABC Tower, Motijheel",
  "city": "Dhaka",
  "area": "Motijheel"
}
```

`201` returns place with `public_id`.

### Set usual preferences

`PUT /user_management/customer/delivery-preferences/`

```json
{
  "lunch_place_id": "<uuid>",
  "dinner_place_id": "<uuid>"
}
```

Same UUID allowed for both. `null` clears that period.

### Weekday overrides (replace-set)

`PUT /user_management/customer/delivery-preferences/day-overrides/`

```json
{
  "overrides": [
    { "meal_period": "lunch", "weekday": 0, "place_id": "<office-uuid>" },
    { "meal_period": "lunch", "weekday": 1, "place_id": "<office-uuid>" }
  ]
}
```

Omitting a weekday means “use usual preference”.

### Preview

`GET /user_management/customer/delivery-preferences/preview/?from=2026-07-27&to=2026-08-02`

Returns a list of `{ service_date, meal_period, place_id, label, full_address, area, city }`.

## Order integration

`generate_order_deliveries` resolves and writes snapshots at create time. Delivery serializers expose snapshot fields to customers and the today board.

Management command:

```bash
python manage.py backfill_delivery_address_snapshots
```

## Migration notes

- `user_management.0007` + `0008` — models + backfill present default → place + lunch/dinner prefs  
- `orders.0007` — snapshot columns on `OrderDelivery`  
- During transition, profile completion `delivery_address` is true if preferences/places exist **or** legacy present default exists  

## How to verify

```bash
python manage.py test user_management.tests.test_delivery_addresses
```
