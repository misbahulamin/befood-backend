# Meal delivery addresses (frontend)

## Summary

Let customers manage **where lunch and dinner go** without flipping a single “default present address” every day.

Mental model (keep the UI this simple):

1. **My places** — save Home, Office, Hostel, …  
2. **Usual delivery** — “Lunch → …”, “Dinner → …” (same place is fine)  
3. **Exceptions (optional)** — “On weekdays, lunch → Office”  
4. **Preview** — show this week’s resolved destinations so users trust the setup  

Do **not** teach customers about resolution precedence.

## Auth

```http
Authorization: Token <token>
```

Base prefix: `/user_management/`

## Integration steps

### Step 1 — My places

1. `GET /user_management/customer/delivery-places/` → list cards  
2. `POST .../delivery-places/` to add  
3. `PATCH .../delivery-places/{public_id}/` to edit  
4. `DELETE .../delivery-places/{public_id}/` — if `400` “in use”, prompt to change lunch/dinner/overrides first  

**Create body**

```json
{
  "label": "Home",
  "full_address": "House 12, Road 5, Mirpur",
  "city": "Dhaka",
  "area": "Mirpur",
  "building_name": "",
  "floor": "",
  "flat_number": "",
  "landmark": ""
}
```

**Response (201)** includes `public_id` — use this UUID everywhere (never integer ids).

Soft limit: **10** active places. Show a friendly message if create returns validation error about the maximum.

### Step 2 — Usual lunch / dinner

`GET /user_management/customer/delivery-preferences/`

```json
{
  "lunch_place_id": "...",
  "dinner_place_id": "...",
  "lunch_place": { "public_id": "...", "label": "Home", "...": "..." },
  "dinner_place": { "...": "..." },
  "updated_at": "..."
}
```

UI: two dropdowns bound to place `public_id`.

`PUT /user_management/customer/delivery-preferences/`

```json
{
  "lunch_place_id": "<home-uuid>",
  "dinner_place_id": "<home-uuid>"
}
```

Saving preferences automatically updates **future scheduled** order deliveries. Past delivered/skipped slots stay as they were.

### Step 3 — Optional weekday exceptions

Hide behind “Different on some days?”.

`GET /user_management/customer/delivery-preferences/day-overrides/`

`PUT` **replaces the full set**:

```json
{
  "overrides": [
    { "meal_period": "lunch", "weekday": 0, "place_id": "<office-uuid>" },
    { "meal_period": "lunch", "weekday": 1, "place_id": "<office-uuid>" },
    { "meal_period": "lunch", "weekday": 2, "place_id": "<office-uuid>" },
    { "meal_period": "lunch", "weekday": 3, "place_id": "<office-uuid>" },
    { "meal_period": "lunch", "weekday": 4, "place_id": "<office-uuid>" }
  ]
}
```

`weekday`: **0 = Monday … 6 = Sunday**.

Example product copy: “Weekdays lunch at Office; weekends use your usual lunch place.”

### Step 4 — Preview strip (recommended)

`GET /user_management/customer/delivery-preferences/preview/?from=2026-07-27&to=2026-08-02`

Use the list to render “Mon lunch → Office, Sat lunch → Home”.

## Order / delivery screens

Order detail `deliveries[]` now includes:

- `delivery_label_snapshot`
- `delivery_full_address_snapshot`
- `delivery_area_snapshot`
- `delivery_city_snapshot`
- optional lat/lng snapshots  

Show these on upcoming and past meal cards. Ops today-board includes label/area/city/full address snapshots too.

## Edge cases / UI states

| Situation | UI |
|-----------|-----|
| No places yet | Empty state → “Add your first place” |
| Preferences empty | Prompt to pick usual lunch/dinner after first place |
| Delete place in use | Explain: change preferences/overrides, then delete |
| Soft cap hit | Disable “Add place” with reason |
| `401` | Re-login |
| `404` on place | Treat as missing / refresh list |

## Legacy transition (present address)

Older clients used **present address + `is_default_delivery`** as the only delivery target.

During transition:

- That API still works for profile/KYC  
- Backend migration (and lazy fallback) maps present default → a delivery place + lunch/dinner prefs  
- Prefer the new places + preferences screens for delivery UX  
- Do not tell users they must “set present as delivery” anymore  

Profile completion still counts delivery as done if either new preferences/places **or** the legacy present default exists.

## Target clients

Mobile and web customer apps (same endpoints). Keep mobile payloads lean: list places with `public_id`, `label`, `area`, `full_address`; nest full place objects only on the preferences GET if useful.
