## Why

Admin and other clients currently receive Bangladesh phone numbers as 10-digit national values from the API and prepend `+880` in the frontend. That splits formatting responsibility across clients, so the same customer can appear with different phone strings on Customers, Orders, Wallet, Kitchen, and print surfaces. Centralizing E.164 display formatting in the backend response layer (without changing stored digits) makes the contract consistent and removes duplicated client-side country-code logic.

## What Changes

- **Centralized BD phone formatters** in backend (`format_bd_phone_e164` for API JSON, `format_bd_phone_readable` for print/email templates): one shared module, no per-endpoint copy-paste.
- **API read responses** that expose customer/user phone (and emergency contact phone where applicable) MUST return `+880XXXXXXXXXX` (E.164-style) instead of bare national digits. Storage and write/validation remain 10 national digits.
- **Search compatibility**: admin `q` (and similar phone search) MUST still match when the operator pastes `+880…` / `880…` / national digits by normalizing the search term before DB lookup.
- **Print / PDF / email**: printable and templated phone strings use a readable form (`+880-XXXX-XXXXXX`) via the shared readable formatter (backend templates) or a thin frontend print helper that does not invent a second country-code source of truth.
- **Frontend (`befood-frontend`)**: remove manual `+880` prepend on admin display paths; render API phone as-is; keep profile edit UX that maps E.164 ↔ `01XXXXXXXXX` for form input/submit without changing the write contract (10 digits).
- **BREAKING (display contract only)**: clients that assumed `phone` response fields were always 10 national digits will now see `+880…`. Write/PATCH bodies and DB storage are unchanged. Document the migration for admin UI and any scripts that concatenated `+880` themselves.

## Capabilities

### New Capabilities

- `api-phone-display-format`: Shared Bangladesh phone display contract — E.164 for JSON API reads, readable hyphenated form for print/email, storage/write remain national 10 digits, search-term normalization for `+880` / `880` prefixes.
- `admin-phone-display-frontend`: Admin (and related) frontend display/print behavior — stop prepending country code; show API E.164 directly; use readable formatting only for print/PDF sheets without breaking table/print layouts.

### Modified Capabilities

- `admin-customer-directory`: Customer list/detail `phone` responses MUST be E.164; phone search MUST accept E.164-prefixed and national forms against stored national digits.
- `admin-customer-frontend-docs`: Document that list/detail phone comes pre-formatted from the API and must not be country-code-prefixed again in the UI.

## Impact

- **Backend (`F:\befood\befood-backend`)**: `user_management/validators.py` (shared formatters + search normalize); serializers/views/services that emit `phone` / `customer_phone` / emergency phone across user_management, orders (incl. kitchen/meal-demand rows), wallet (funding lists, invoices, notifications), and profile APIs; tests asserting E.164 / readable output and search.
- **Frontend (`F:\befood\befood-frontend`)**: Admin Customers / Customer Detail, Orders, Wallet funding labels, Kitchen order details print sheet, WhatsApp helpers (accept E.164 without double-prefix); profile phone display helpers that strip country code only for editable `01…` fields; remove obsolete `+880` concatenation.
- **Data**: No migration of stored phone values (`CustomerProfile.phone` and related remain 10 digits).
- **Out of scope**: Multi-country dial plans beyond BD `+880`, changing write validation length, SMS gateway payload redesign, deliveryman-app unrelated hardcoded support numbers.
- **Cross-repo note**: OpenSpec lives in `befood-backend`; frontend tasks are implemented under `befood-frontend` and tracked via the frontend capability.
