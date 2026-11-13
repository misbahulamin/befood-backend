# Tasks

## 1. Snapshot model + address service

- [x] 1.1 Add `delivery_building_name_snapshot`, `delivery_floor_snapshot`, and `delivery_flat_number_snapshot` (blank CharFields) on `OrderDelivery` with a migration; verify `makemigrations`/`migrate` succeed locally
- [x] 1.2 Extend `snapshot_fields_from_place` (and resync/backfill `update_fields` lists) to copy `building_name` / `floor` / `flat_number`; verify a unit test that place → snapshot dict includes the three values (and empty place → empty strings)

## 2. Today-board payload

- [x] 2.1 Add `delivery_place` to the board delivery queryset `select_related`; when building each customer row, set `building_name` / `floor` / `flat_number` (prefer non-empty snapshots, else live place, else `""`); verify board/API test asserts Abdul-style place parts appear and street `full_address` still works
- [x] 2.2 Add a test case where structured parts are missing and verify the three keys are present as empty strings without inventing values

## 3. Frontend docs

- [x] 3.1 Update `delivery_zones/docs/frontend/zone-based-delivery.md` customer example (and `deliveryman-today-ops.md` if it lists customer fields) to document `building_name`, `floor`, `flat_number`; verify the docs mention empty-string semantics

## 4. Integration check

- [x] 4.1 Run the affected delivery_zones / orders address tests and fix regressions from the new columns and board keys
- [ ] 4.2 Manual smoke against a customer like Abdul Baser: today-board JSON includes Building / Floor / Flat; confirm deliveryman mobile detail sheet shows them after API deploy

## Workflow follow-up

- Archive this change after review.
- No mobile code change expected if `delivery-contact-address-ui` is already shipped; verify on device after backend deploy.
