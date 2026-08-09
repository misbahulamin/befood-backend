# Customer Frontend — Delivery Box & Service Area

## Summary

Wire the Home/Root **Delivery ঠিকানা** box to browser/device geolocation and `POST /api/v1/service-areas/check/`. Final coverage is **always** decided by the backend. Do **not** use IP geolocation. Do **not** implement `if (distance <= radius) allowCheckout()` in the client.

Target client: customer web (`befood_frontend`).

## Base path & headers

- Check: `POST /api/v1/service-areas/check/`
- Demand: `POST /api/v1/service-areas/demand/`
- Optional: `Authorization: Token <token>`
- Guest: `X-Guest-Session-Id: <uuid>` (persist in `localStorage`)
- Optional: `X-Client-Type: web` | `mobile`

## Recommended call order

1. On first Home visit or Delivery box click → request browser `navigator.geolocation`.
2. Show permission copy (Bangla UX as product copy).
3. On allow → loading “খোঁজা হচ্ছে…” → collect `latitude`, `longitude`, `accuracy`, `timestamp`.
4. Optional reverse geocode (Google) → `location_name`.
5. `POST /check/` → loading “যাচাই করা হচ্ছে…”.
6. Render result states from response.
7. On checkout / order create → backend revalidates; handle order errors.

## Request body

```json
{
  "latitude": 22.3569,
  "longitude": 91.7832,
  "accuracy": 18,
  "location_name": "GEC Circle, Chattogram",
  "guest_session_id": "optional-if-not-in-header"
}
```

`location_name` may be `null`.

## UI states

| State | Condition | UI |
|-------|-----------|-----|
| Permission denied | geolocation denied | “Location access দেওয়া হয়নি” + “ম্যানুয়ালি ঠিকানা নির্বাচন করুন” |
| Detecting | awaiting GPS | “আপনার অবস্থান খোঁজা হচ্ছে...” |
| Verifying | awaiting API | “আপনার এলাকায় BeFood-এর সেবা যাচাই করা হচ্ছে...” |
| Available + name | `service_available` + name | Delivery to `{name}` ✓ Service Available |
| Available no name | `service_available` | বর্তমান অবস্থান ✓ BeFood Service Available |
| Unavailable | `!service_available` | Sorry + nearest hub name + `distance_km` + CTA “আমার এলাকায় BeFood চাই” → `POST /demand/` |
| Low accuracy | `location_reliable === false` | Retry GPS + “Map থেকে নির্বাচন করুন” |

## Manual fallbacks

1. Current location (geolocation)
2. Address search → resolve to lat/lng → check
3. Map pin → move marker → check with lat/lng (omit `accuracy` or send map accuracy)

## Cache rules

Cache last verification: coords, name, accuracy, hub id, `service_available`, `verified_at`.

Re-check when:

- User changes location manually
- Cache older than TTL (suggest 24h)
- Checkout / order create (always trust server order response)

## Checkout

Order create must send normal order payload; **do not** send a client `service_available` flag as authority. If backend rejects with delivery/service-area errors, show Bangla copy and send user back to delivery box / map pin.

Before package order create, ensure the selected delivery place(s) persist **latitude** and **longitude** (delivery-place write API already accepts both fields). Text-only addresses will fail the server gate.

### Order create error codes

| `error_code` | Meaning | Suggested Bangla UX |
|--------------|---------|---------------------|
| `DELIVERY_LOCATION_REQUIRED` | Delivery place missing lat/lng | ম্যাপ/GPS দিয়ে ডেলিভারি লোকেশন সেট করুন |
| `SERVICE_AREA_UNAVAILABLE` | Coords outside all active hubs | এই লোকেশনে BeFood সার্ভিস নেই — চাইলে “আমার এলাকায় BeFood চাই” |

Read `error_code` from the order-create validation error payload (may appear alongside `non_field_errors`). Do not unlock checkout from a successful `demand` call.

## API outage handling

If check/demand returns HTML 404 (route missing on server), show a temporary “সার্ভিস যাচাই করা যাচ্ছে না” state — do not invent local coverage.

## Security

- Backend Haversine + active hubs only.
- Client never final-gates packages/subscriptions/checkout by local distance math.
