## Why

GPS/browser clients often send latitude/longitude with more than 6 decimal places (float noise such as `31.915129999999998`). DRF `DecimalField(max_digits=9, decimal_places=6)` then rejects with “Ensure that there are no more than 9 digits in total,” so customers cannot add a delivery place even when the coordinate is valid on Earth.

## What Changes

- Quantize inbound lat/lng to 6 decimal places (~0.11 m) before digit validation on delivery-place and location-preference serializers.
- Quantize in shared `validate_coordinates` so service-layer / service-area paths stay consistent.
- Add a regression test using high-precision GPS floats (China/urban style values).

## Capabilities

### New Capabilities
- `coordinate-input-quantization`: Accept high-precision client coordinates by rounding to stored precision without rejecting valid WGS84 points.

### Modified Capabilities
- `delivery-address-book`: Create/update delivery places MUST accept GPS floats that exceed 9 total digits before quantization.

## Impact

- `user_management` serializers (delivery place write, location refresh/save-as-place)
- `service_area.services.geo.validate_coordinates` (and thus check API)
- Optional shared serializer field for reuse
- Frontend may keep sending full GPS precision; backend normalizes
