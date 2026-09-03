# Guest location offer resolution (backend)

## Quick summary

| Piece | Location |
|-------|----------|
| Durable accept/decline/suppress | `GuestLocationOfferResolution` |
| Offer lookup / accept / decline | `user_management/services/location_preference.py` |
| API | `GET/POST .../guest-offer/`, `POST .../guest-offer/decline/` |
| Confirmation flags | `has_saved_location` / `location_confirmed` on preference (+ lean login/`me` summary) |

## Permissions

| Endpoint | Auth |
|----------|------|
| Guest offer GET/POST/decline | `HasCustomerProfile` |

## State machine

```text
(no resolution) + ServiceAreaRequest exists
  → pending (exists=true)
  → accept → status=accepted (place created, preference saved)
  → decline → status=declined (no place)
  → duplicate radius match → status=suppressed (idempotent on GET)

Later GET for same (customer, guest_session_id) → exists=false
```

## Business rules

1. Resolutions are per `(customer_profile, guest_session_id)`; guest `ServiceAreaRequest` history is not deleted.
2. `location_confirmed` means active preference has saved lat/lng — not `is_verified_location`.
3. DELETE location-preference clears saved fields and sets confirmation flags false; places remain.
4. Accept of an already-resolved offer returns `409 GUEST_OFFER_ALREADY_RESOLVED` (or `422 LOCATION_ALREADY_EXISTS` when suppressed as duplicate).
5. Decline is idempotent and does not create a place.

## Verify

```bash
python manage.py test user_management.tests.test_customer_location --keepdb
```

Frontend contract: `user_management/docs/frontend/customer-location-preference.md`.
