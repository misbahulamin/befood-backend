## 1. Quantization helpers

- [ ] 1.1 Quantize lat/lng to 6 dp inside `service_area.services.geo.validate_coordinates`
- [ ] 1.2 Add shared `CoordinateDecimalField` that quantizes before DRF digit checks

## 2. Wire serializers

- [ ] 2.1 Use `CoordinateDecimalField` on delivery-place write and location preference refresh/save-as-place serializers
- [ ] 2.2 Use the same field (or equivalent) on service-area check request lat/lng for consistency

## 3. Tests & docs

- [ ] 3.1 Regression test: delivery-place create with `31.915129999999998` succeeds
- [ ] 3.2 Note in frontend location doc that backend accepts excess GPS precision
