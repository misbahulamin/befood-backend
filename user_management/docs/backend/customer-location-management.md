# Customer location management (backend)

## Quick summary

| Piece | Location |
|-------|----------|
| Place metadata | `CustomerDeliveryPlace.location_source` (+ accuracy, formatted_address, is_verified_location) |
| Detected vs saved cache | `CustomerLocationPreference` |
| Admin knobs | `CustomerLocationSettings` singleton |
| Helpers | `user_management/services/location_service.py` |
| Place rules | `user_management/services/delivery_place.py` |
| Preference flows | `user_management/services/location_preference.py` |
| Guest offer resolution | `GuestLocationOfferResolution` + `docs/backend/guest-location-offer-resolution.md` |

## Permissions

| Endpoint | Auth |
|----------|------|
| Customer location-preference* | `HasCustomerProfile` |
| Delivery places | `HasCustomerProfile` |
| Admin location-settings | `IsVerifiedAdmin` |

## Business rules

1. Geo sources `gps|map_pin|search|guest_migration` require lat+lng and address text.
2. Duplicate: Haversine ≤ `duplicate_radius_km`; on update exclude current place pk.
3. Max active places from settings; code `ADDRESS_LIMIT_REACHED`; no auto-delete of grandfathered rows.
4. Refresh updates detected fields only; save-as-place creates `CustomerDeliveryPlace`.
5. Meal lunch/dinner change only when explicit flags are true.
6. Accuracy > `SERVICE_AREA_ACCURACY_THRESHOLD_M` → soft `LOW_LOCATION_ACCURACY` / `warning_code`.

## Verify

```bash
python manage.py test user_management.tests.test_delivery_addresses user_management.tests.test_customer_location service_area.tests.test_service_area
```

Frontend contract: `user_management/docs/frontend/customer-location-preference.md`.
