## Why

After login, customers repeatedly see the Bangla guest-location offer popup asking whether to save a previously used location as a delivery address—even after they already accepted or declined. Root cause: `GET .../guest-offer/` returns `exists: true` whenever any `ServiceAreaRequest` exists for the persistent guest session id, while accept/decline never mark that offer as resolved. This harms UX and must be fixed with durable state, not by hiding the dialog alone.

## What Changes

- Persist guest-location offer resolution on the backend (accepted or declined) so subsequent `GET .../guest-offer/` returns `exists: false` for that guest session (and/or customer).
- After successful accept, treat the offer as consumed; do not re-offer the same guest session history on later logins.
- After explicit decline, record a durable dismissal so the same offer does not reappear across login/logout/app restart.
- Suppress the offer when the authenticated customer already has an equivalent saved delivery place / active saved location preference for that guest history.
- Expose clear client-facing confirmation/saved-location status so mobile and web can decide without guessing (e.g. `exists`, resolution state, `has_saved_location`).
- Optionally include a lean location-confirmation summary on login/`me` so clients need fewer round-trips (additive, non-breaking).
- Update customer client docs for mobile (`befood_mobile`) and web (`befood-frontend`) so they: skip popup when offer is not pending; rotate/clear guest session after accept or decline; never rely on in-memory-only dismissal.
- Do **not** break existing delivery places, meal delivery preferences, order delivery snapshots, or service-area check/checkout gates.

## Capabilities

### New Capabilities
- `guest-location-offer-lifecycle`: Durable accept/decline resolution for guest→login location migration offers; corrected `exists` semantics; duplicate/already-saved suppression.
- `location-confirmation-status`: Clear API fields for saved vs pending confirmation so clients can skip repeated prompts.
- `guest-location-offer-client-docs`: Cross-client (mobile + customer web) contract for when to show/skip the popup and how to clear guest session state.

### Modified Capabilities
- *(none in `openspec/specs/` — guest migration lives only under completed change `customer-location-management`; this change introduces additive lifecycle/status capabilities rather than editing archived main-spec names.)*

## Impact

- **Backend:** `user_management/services/location_preference.py` (`get_guest_location_offer`, `accept_guest_location_offer`), `delivery_views.py` guest-offer endpoints, possibly new model fields or resolution table on `CustomerLocationPreference` / guest-offer claim records; tests in `test_customer_location.py`; docs under `user_management/docs/frontend/`.
- **APIs:** `GET/POST .../location-preference/guest-offer/` behavior change for `exists` after resolve; optional `POST .../guest-offer/decline/` (or POST with action); optional additive fields on login/`me` and `GET location-preference/`.
- **Mobile:** `befood_mobile` login success → `maybeShowGuestLocationOffer`; `CustomerLocationCubit`; guest session cache.
- **Web:** `befood-frontend` `GuestLocationOfferListener` / modal (customer SPA; admin unaffected).
- **Out of scope:** Admin UI, rider location, checkout service-area re-verification semantics, renaming `is_verified_location` (remains technical geo verification).
