## 1. Backend data model

- [x] 1.1 Add `GuestLocationOfferResolution` (or equivalent) model: unique `(customer_profile, guest_session_id)`, `status` (`accepted`|`declined`|`suppressed`), `resolved_at`, optional FKs/refs to request/place
- [x] 1.2 Create and apply migration; register model in Django admin for support visibility

## 2. Backend guest-offer lifecycle

- [x] 2.1 Update `get_guest_location_offer` to require authenticated `customer_profile` and return `exists: false` when resolution exists
- [x] 2.2 Suppress pending offer when guest coords match an existing active place / saved preference within duplicate radius; set status `suppressed` (idempotent upsert recommended)
- [x] 2.3 On successful `accept_guest_location_offer`, upsert resolution `accepted`
- [x] 2.4 Add authenticated decline endpoint (`POST .../guest-offer/decline/` or documented equivalent) that upserts `declined` without creating a place
- [x] 2.5 Include explicit `status` on guest-offer GET responses (`pending`|`accepted`|`declined`|`suppressed`|`none`)
- [x] 2.6 Wire URLs, serializers, OpenAPI helpers for decline + updated GET contract

## 3. Backend confirmation status

- [x] 3.1 Add additive `has_saved_location` / `location_confirmed` (documented names) to `GET location-preference/` payload
- [x] 3.2 Optionally add lean `location_confirmation` summary on login/`me` without breaking existing fields
- [x] 3.3 Ensure clearing active saved preference via existing DELETE preference correctly flips confirmation flags

## 4. Backend tests

- [x] 4.1 Test accept then GET → `exists: false` across simulated re-login
- [x] 4.2 Test decline then GET → `exists: false`; decline does not create place
- [x] 4.3 Test duplicate/equivalent saved place suppresses offer
- [x] 4.4 Test first-time pending offer still returns `exists: true`
- [x] 4.5 Test preference confirmation flags and (if enabled) login/`me` summary

## 5. Backend docs

- [x] 5.1 Update `user_management/docs/frontend/customer-location-preference.md`: decline API, status enum, skip conditions, session rotate guidance
- [x] 5.2 Add/update backend technical note under `user_management/docs/backend/` for resolution model and flows

## 6. Mobile app (`F:\befood\befood_mobile`)

- [x] 6.1 Call decline API from `declineGuestOffer` / dialog “এখন নয়” path (stop memory-only dismiss)
- [x] 6.2 After accept or decline success, clear/rotate `befood_guest_session_id` in `service_area_cache`
- [x] 6.3 Keep `maybeShowGuestLocationOffer` gated strictly on GET `exists: true`; skip otherwise
- [x] 6.4 Verify login-only trigger still works for first pending offer; confirm save-confirm manual flow unchanged
- [x] 6.5 Add/adjust Flutter tests or manual QA checklist for accept/decline → no re-prompt on next login

## 7. Customer web (`F:\befood\befood-frontend`)

- [x] 7.1 Update `GuestLocationOfferListener` to call decline API (replace or augment sessionStorage-only dismiss)
- [x] 7.2 Clear/rotate guest session id after accept or decline
- [x] 7.3 Skip modal when GET `exists: false`; keep `SaveLocationAsPlaceModal` manual flow unchanged
- [x] 7.4 Smoke-test login → pending → resolve → re-login does not re-open guest offer modal

## 8. Verification

- [x] 8.1 Run backend customer location tests and fix regressions
- [x] 8.2 End-to-end checklist: guest check → login → accept → logout → login (no popup); same for decline; manual location change still confirms
