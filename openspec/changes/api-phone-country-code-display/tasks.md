## 1. Backend shared formatters

- [x] 1.1 Add/confirm `format_bd_phone_e164`, `format_bd_phone_readable`, and `normalize_phone_search_term` in `user_management/validators.py` (storage stays 10 national digits; no DB migration)
- [x] 1.2 Add unit tests in `user_management/tests/test_phone_validators.py` for national → E.164, idempotent E.164/`880…` inputs, empty/null, readable `+880-XXXX-XXXXXX`, and search-term stripping

## 2. Wire E.164 on API / service emission points

- [x] 2.1 Admin customer list/detail serializers: return `phone` via `format_bd_phone_e164`; normalize admin `q` phone search with `normalize_phone_search_term`
- [x] 2.2 Customer profile / auth payloads: format `phone` and `emergency_contact_phone` on reads; keep write validation as 10 digits
- [x] 2.3 Orders: format `customer_phone` (and any other customer phone fields) in order serializers
- [x] 2.4 Meal demand / kitchen customer rows: format `phone` in `orders/services/meal_demand.py` dict builders
- [x] 2.5 Wallet: format funding/list `customer_phone` in serializers; use `format_bd_phone_readable` in invoice PDF context, recharge notification templates, and wallet-balance threshold copy
- [x] 2.6 Grep remaining customer phone emissions; replace inline `+880` concatenation with shared helpers (optional: deliveryman profile phone if touched)

## 3. Backend tests and docs

- [x] 3.1 Update API tests (admin customers, profile, meal demand, wallet notifications) to expect E.164 / readable forms; keep storage/write assertions on national digits
- [x] 3.2 Update OpenAPI examples and `user_management/docs/frontend/admin-customer-management.md` so list/detail `phone` is documented as E.164 with no client-side country-code prepend

## 4. Frontend display and print (`befood-frontend`)

- [x] 4.1 Remove manual `+880` prepend on admin Customers / related display paths; render API phone as-is
- [x] 4.2 Ensure Orders, Wallet funding labels, and WhatsApp helpers accept E.164 without double-prefixing
- [x] 4.3 Apply `formatBdPhoneReadable` (or equivalent) only on print/PDF sheets (e.g. kitchen order details); preserve existing print table layout
- [x] 4.4 Keep profile edit helpers (`formatBdPhoneDisplay` / `toApiPhone`) mapping E.164 ↔ local `01…` / national write payload
- [x] 4.5 Update frontend unit tests for phone display, print readable form, funding labels, and WhatsApp digit conversion

## 5. Validation

- [x] 5.1 Run targeted backend tests for phone validators, admin customers, profile, meal demand phone rows, and wallet notification/invoice phone context
- [x] 5.2 Run targeted frontend phone-related unit tests
- [x] 5.3 Smoke-check Admin Customers, one order/wallet phone surface, and one print sheet for consistent formatting without double `+880`
