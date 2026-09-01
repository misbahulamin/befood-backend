## Context

`CustomerDeliveryPlace.latitude/longitude` and related APIs use `Decimal(max_digits=9, decimal_places=6)`. That storage precision is correct for delivery (~11 cm). Clients (Geolocation API) often post JSON numbers with 12+ significant digits, which fail DRF digit checks before business logic runs. UI shows: `latitude: Ensure that there are no more than 9 digits in total.`

## Goals / Non-Goals

**Goals:**
- Accept valid WGS84 coordinates regardless of excess fractional digits.
- Persist quantized 6-decimal values matching the DB schema.
- Cover delivery-place create and location preference refresh/save paths.

**Non-Goals:**
- Changing DB column precision.
- Changing service-area hub schemas beyond shared validate_coordinates quantization.
- Frontend-only rounding (backend must remain defensive).

## Decisions

### 1. Quantize at serializer + geo validate
- **Choice:** Introduce a small `CoordinateDecimalField` (max_digits=9, decimal_places=6) that quantizes with `ROUND_HALF_UP` to `0.000001` before parent validation; also quantize inside `service_area.services.geo.validate_coordinates`.
- **Rationale:** Serializer is where the user-visible error originates; geo validate covers service calls that bypass those fields.
- **Alternatives considered:** Raise `max_digits` only on serializers — still fails model save if unquantized. Reject and ask client to round — worse UX.

## Risks / Trade-offs

- [Sub-meter rounding] → Acceptable for meal delivery; 6 dp is intentional.
- [Service-area check also rounds] → Consistent with place storage; negligible for hub radius km math.

## Migration Plan

No DB migration. Deploy code; existing rows unchanged.

## Open Questions

None.
