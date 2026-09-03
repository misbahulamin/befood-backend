## Context

BeFood already supports guest service-area checks, post-login guest location migration (`GET/POST .../location-preference/guest-offer/`), delivery places, and `CustomerLocationPreference` (saved vs detected). The Bangla popup after login is the **guest-offer** dialog (mobile + customer web), not the separate “save current GPS” confirm.

Today `get_guest_location_offer(guest_session_id)` returns `exists: true` whenever any `ServiceAreaRequest` exists for that guest id. Accept creates a place but does not consume the offer. Decline is client-only (memory / sessionStorage). Guest session ids persist in local storage across logout. Result: every login re-prompts.

Constraints: do not break delivery places, meal preferences, order snapshots, or checkout service-area re-checks. Prefer additive API fields. Implementation spans backend (`befood-backend`), Flutter (`befood_mobile`), and customer web (`befood-frontend`); OpenSpec lives in the backend repo with client docs as the contract for the other repos.

## Goals / Non-Goals

**Goals:**

- Persist offer resolution (accepted / declined) per authenticated customer + guest session.
- Make `GET guest-offer` return `exists: false` when the offer is already resolved or when the customer already has an equivalent saved delivery location for that history.
- Expose clear confirmation/saved-location status for clients.
- Document and align mobile + web so they call decline, rotate guest session after resolve, and never show the popup when `exists` is false.
- Keep first-time offer and manual location-change flows intact.

**Non-Goals:**

- Changing OS GPS permission UX beyond guest-offer repetition.
- Auto-setting lunch/dinner defaults on guest accept (existing opt-in flags stay).
- Admin UI / rider location.
- Replacing `is_verified_location` with UX confirmation semantics.
- Removing checkout re-verification of service area.

## Decisions

### 1. Durable offer resolution table (preferred over mutating ServiceAreaRequest)

**Choice:** Add `GuestLocationOfferResolution` (name may vary) with unique `(customer_profile, guest_session_id)`, fields: `status` (`accepted` | `declined`), `resolved_at`, optional `service_area_request_id` / place public id when accepted.

**Why:** Guest checks are shared audit history; deleting or flipping `ServiceAreaRequest` would break analytics and multi-account use of the same device guest id. Per-customer resolution is the correct scope.

**Alternatives considered:**

- Flag on `ServiceAreaRequest` → wrong ownership (guest row is not per-customer).
- Client-only SharedPreferences / sessionStorage → web already has session decline; mobile memory-only decline fails across logins; not production-durable across devices.
- Clear guest session only on client → helps one device but not if client forgets; backend still returns `exists: true`.

### 2. Authenticated GET semantics

**Choice:** `get_guest_location_offer` MUST receive the authenticated `customer_profile` (in addition to `guest_session_id`) and return `exists: false` when:

1. No matching `ServiceAreaRequest`, or
2. A resolution row exists for `(customer, guest_session_id)`, or
3. Customer already has active saved location preference (`saved.exists`) **and** the latest guest check coordinates fall within duplicate radius of an existing active delivery place (or of the saved preference coords)—treat as already confirmed / no offer needed.

**Why:** Matches product: once confirmed or already saved equivalently, never re-prompt. Pure “any saved place exists” without coordinate match may over-suppress a legitimate first guest migration when the user has an unrelated address—prefer duplicate-radius / equivalent-location suppression plus explicit resolution.

**API response (additive):** When pending, keep existing payload and add `status: "pending"`. When not pending, `{ "exists": false, "status": "accepted"|"declined"|"suppressed"|"none" }` as applicable (document exact enum in specs).

### 3. Explicit decline endpoint

**Choice:** Add `POST .../location-preference/guest-offer/decline/` (or same path with `{ "action": "decline", "guest_session_id" }`) that upserts resolution `declined`. Accept continues to upsert `accepted`.

**Why:** Current docs say “decline (no call)” which cannot be durable server-side. Breaking soft contract for clients that ignore decline is acceptable because behavior today is already wrong across sessions; document migration: clients MUST call decline.

### 4. Location confirmation status exposure

**Choice:**

- Treat **location confirmed for delivery UX** as: active `CustomerLocationPreference` with `saved.exists == true` (and/or active delivery place). Do **not** overload `is_verified_location`.
- Enrich `GET location-preference/` with additive flags such as `has_saved_location`, `location_confirmed` (alias of saved exists + active), `guest_offer_pending` only if client also passes guest session (optional; otherwise keep guest-offer as separate call).
- Optional additive lean summary on login/`me`: `location_confirmation: { has_saved_location, location_confirmed }` without full preference payload—clients may still call guest-offer when they hold a guest session id.

**Why:** Login today returns no location state; clients need a single source of truth without inventing flags.

### 5. Client responsibilities (mobile + web)

**Choice:** After accept **or** decline success:

1. Trust backend `exists: false` on later logins.
2. Rotate or clear local `guest_session_id` so future guest browsing starts a fresh session.
3. Do not show popup unless GET returns `exists: true` / `status: pending`.
4. Manual location change continues to use save-as-place / save-confirm flows (unchanged).

**Why:** Defense in depth: backend is source of truth; client rotation prevents accidental reattachment to old guest history for *other* accounts on the same device.

### 6. Scope of code changes across repos

**Choice:** Implement backend + docs in this repo first; track Flutter and React tasks in `tasks.md` with explicit paths. Spec `guest-location-offer-client-docs` is the contract those apps must follow.

## Risks / Trade-offs

- **[Risk] Soft contract break:** Clients that decline without calling API still re-prompt until updated. → **Mitigation:** Ship backend first (accept still stops repeat after accept once resolution is written); ship client decline call + session rotate in same release window; document clearly.
- **[Risk] Shared device guest id across two customer accounts:** Resolution is per customer, so account B may still see an offer for the same guest history—correct. After B declines/accepts, B stops; A already resolved stays resolved.
- **[Risk] Over-suppression via “any saved place”:** → **Mitigation:** Prefer resolution rows + duplicate-radius equivalence, not blanket “has any place.”
- **[Risk] Migration of users already stuck re-prompting:** Accepting again may 422 `LOCATION_ALREADY_EXISTS`. → **Mitigation:** On GET, if duplicate place already exists, return `exists: false` / `status: suppressed` and optionally auto-write `accepted` resolution for idempotency.
- **[Trade-off] Extra table vs fields on preference:** Preference is 1:1 with customer and cannot store multiple guest session resolutions. Table is required.

## Migration Plan

1. Add model + migration; deploy backend (additive).
2. Update `get_guest_location_offer` / accept / new decline; tests for accept→GET false, decline→GET false, duplicate suppress.
3. Update frontend docs + OpenAPI.
4. Release mobile + web: call decline, rotate guest session, skip UI when not pending.
5. Rollback: feature is additive; reverting code leaves resolution rows harmless; clients fall back to old behavior only if GET logic reverted.

## Open Questions

- Exact path for decline (`.../decline/` vs action field)—default to dedicated `POST .../guest-offer/decline/` for clarity.
- Whether login/`me` summary is required in v1 or deferred to preference + guest-offer only—default: include lean summary if low cost; otherwise document preference GET as primary.
- Whether auto-writing `accepted` resolution when GET detects duplicate place should happen on read (side effect) or only on a dedicated reconcile—prefer **write on GET only if carefully documented**, else compute `suppressed` without write and write resolution on next accept/decline attempt; **recommended:** upsert `accepted` (or `suppressed`) inside GET when duplicate detected to permanently stop prompts (idempotent).
