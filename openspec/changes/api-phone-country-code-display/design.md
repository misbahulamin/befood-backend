## Context

Bangladesh customer phones are stored as **10 national digits** on `CustomerProfile.phone` (and related fields such as `emergency_contact_phone`), validated by `validate_bangladesh_phone`. Read APIs historically returned those digits unchanged; admin UI and other clients prepended `+880` for display. That client-side rule drifted across Customers, Orders, Wallet, Kitchen/meal-demand rows, invoices, and print sheets.

Partial shared helpers already exist or are in progress under `user_management.validators` (`format_bd_phone_e164`, `format_bd_phone_readable`, `normalize_phone_search_term`). This design standardizes their use at every response/template emission point and aligns frontend so it **displays** API values instead of inventing country codes.

Stakeholders: admin operators (list/detail/print), kitchen print sheets, wallet invoice/email, customer profile forms (edit still uses `01…` UX), backend maintainers (one formatter).

Constraints: no DB migration of phone values; write bodies stay 10 digits; OpenSpec repo-local to `befood-backend` with frontend work in `befood-frontend`; follow DRF service/serializer layering.

## Goals / Non-Goals

**Goals:**

- Single E.164 display string for JSON phone fields: `+880` + 10 national digits
- Single readable string for print/email: `+880-XXXX-XXXXXX`
- Apply formatters in serializers/services that emit phone — never duplicate `'+880' + phone` inline
- Admin search accepts pasted E.164 / `880…` / national forms against stored national digits
- Frontend stops prepending `+880` on admin display; print uses readable helper only as presentation
- Profile edit continues to show/submit local `01…` / national write shape via existing `formatBdPhoneDisplay` / `toApiPhone`

**Non-Goals:**

- Changing storage schema or backfilling phones
- Multi-country dial plans beyond BD `+880`
- Changing SMS/OTP gateway payloads (out of scope unless they already use the same helpers)
- New API fields such as `phone_e164` alongside `phone` (format the existing field)
- Reworking hardcoded marketing/support `tel:` links unrelated to customer records

## Decisions

### 1. Format at the response layer; keep storage national

**Choice:** Keep DB and write validation as 10 digits. Apply `format_bd_phone_e164` in `SerializerMethodField` getters, auth/profile payload builders, and dict-building services (e.g. meal-demand customer rows). Use `format_bd_phone_readable` only for human documents (invoice PDF context, email templates, threshold notification copy).

**Rationale:** Avoids migration risk and keeps PATCH/POST contracts stable. Display contract changes on the same field name (`phone` / `customer_phone`) — documented as a display **BREAKING** change for clients that concatenated `+880` themselves.

**Alternatives considered:**

- Persist E.164 in DB — cleaner long-term, but forces migration, unique-index rewrite, and write-path churn for little operator benefit now.
- Add parallel `phone_display` field — additive but doubles surface area; clients would still need to know which field to use.

### 2. One shared module in `user_management.validators`

**Choice:** Own formatters next to `validate_bangladesh_phone` (already the phone domain gate). Other apps import from there.

**Rationale:** Phone validation already lives here; importing from `user_management` into orders/wallet matches existing cross-app patterns.

**Alternative:** `common/phone.py` — nicer purity, but extra module without a clear home unless more countries appear.

### 3. Idempotent formatters

**Choice:** `format_bd_phone_e164` accepts national 10, `880…` 13, or already-`+880…` 14 and returns canonical `+880XXXXXXXXXX`. Empty → `None`. Non-conforming → stripped raw (no crash). Readable formatter normalizes via E.164 first, then inserts hyphens.

**Rationale:** Safe during rollout if some paths already return E.164; protects legacy dirty rows from 500s.

### 4. Search normalization, not stored E.164 matching

**Choice:** `normalize_phone_search_term` strips leading `+880` / `880` before admin `q` icontains (or equivalent) against stored national digits.

**Rationale:** Storage stays national; operators can paste WhatsApp/E.164 strings from the UI.

### 5. Frontend: display as-is; readable only for print

**Choice:** Admin tables/detail show API `phone` unchanged. Print/PDF (`KitchenOrderDetailsPrintSheet`, similar sheets) call `formatBdPhoneReadable` which accepts E.164 (and legacy national for safety). Remove any `'+880' + phone` prepend helpers on display paths. WhatsApp URL builders accept E.164 without double-prefixing. Profile forms keep `formatBdPhoneDisplay` → `01…` for inputs and `toApiPhone` → 10 digits on submit.

**Rationale:** Backend is source of truth for dialable E.164; print needs extra readability without a second country-code invention; edit UX still expects local leading-zero entry.

### 6. Coverage inventory (apply everywhere customer phone is emitted)

| Area | Mechanism |
|------|-----------|
| Admin customer list/detail | `admin_customer_serializers` |
| Customer/auth profile payloads | profile serializers, auth_service |
| Orders admin (`customer_phone`) | order serializers |
| Meal demand / kitchen customer rows | `meal_demand` dict builder |
| Wallet funding / admin lists | wallet serializers |
| Invoices / recharge emails / balance alerts | `format_bd_phone_readable` in services |

Deliveryman profile responses MAY reuse the same E.164 helper for consistency when they expose `phone`; not required for the customer admin goal but preferred if touched.

## Risks / Trade-offs

- **[Risk] Clients that prepend `+880` will show `+880+880…`** → Mitigation: ship frontend changes in the same release window; grep frontend for `+880` concatenations; keep formatters idempotent so double application in backend is harmless.
- **[Risk] Tests asserting bare 10-digit phone strings fail** → Mitigation: update API tests to expect E.164; keep write/storage tests on national digits.
- **[Risk] Search regressions if normalize is too aggressive** → Mitigation: only strip when prefix matches `+880`/`880` with digit remainder; unit-test edge cases.
- **[Trade-off] Same field name, new format** → Clearer than dual fields; requires client awareness (documented BREAKING display contract).

## Migration Plan

1. Land backend formatters + wire all emission points; update OpenAPI examples and backend tests.
2. Deploy backend (responses become E.164).
3. Deploy frontend that stops prepending and uses readable print helper.
4. Rollback: revert serializer wiring (storage unchanged); frontend can temporarily tolerate both shapes via existing readable/display helpers that already accept national and E.164.

## Open Questions

- None blocking: BD-only `+880` is fixed for current product scope. Multi-country can revisit storage of dial code later.
