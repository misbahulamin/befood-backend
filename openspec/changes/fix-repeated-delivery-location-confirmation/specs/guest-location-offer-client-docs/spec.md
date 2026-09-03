## ADDED Requirements

### Requirement: Show guest offer popup only when backend says pending
Customer mobile and customer web clients MUST show the post-login guest location confirmation popup only when `GET .../guest-offer/` returns `exists: true` (pending). Clients MUST NOT show that popup solely because a local guest session id exists or because a prior in-memory flag was unset.

#### Scenario: Skip popup when exists false
- **WHEN** login succeeds and guest-offer GET returns `exists: false`
- **THEN** the client continues to the normal post-login destination without showing the guest-offer dialog

#### Scenario: Show popup when pending
- **WHEN** login succeeds and guest-offer GET returns `exists: true` with pending status
- **THEN** the client may show the confirmation dialog once for that pending offer

### Requirement: Decline must call the backend
When the user chooses not to save the guest location (“এখন নয়” / equivalent), the client MUST call the authenticated decline API for that `guest_session_id` and MUST NOT rely only on clearing local/dialog state.

#### Scenario: Decline persists across re-login
- **WHEN** the user declines the offer and later logs out and logs in with the same device guest session still present
- **THEN** the client either receives `exists: false` from the backend or otherwise does not show the popup again for that resolved offer

### Requirement: Rotate or clear guest session after resolve
After a successful accept or decline, the client MUST clear or rotate the locally stored guest session id so subsequent anonymous browsing does not reuse the consumed session for offer prompts.

#### Scenario: Fresh guest session after accept
- **WHEN** accept succeeds
- **THEN** the client replaces or removes the stored guest session id before the next guest service-area check

### Requirement: Manual location change keeps its own confirm flow
Clients MUST continue to use the existing save-location confirmation flow when the user manually changes or selects a new delivery location. Resolving a guest offer MUST NOT disable manual save/confirm UX.

#### Scenario: User changes location later
- **WHEN** a user with a confirmed saved location opens location options and chooses a new place to save
- **THEN** the normal save-confirm UI may appear and save-as-place APIs remain available

### Requirement: Documentation targets both clients
Backend frontend docs for this change MUST describe the updated guest-offer lifecycle, decline API, confirmation status fields, and the required mobile + web client steps (check GET → show/skip → accept/decline → rotate session).

#### Scenario: Doc lists skip conditions
- **WHEN** a client integrator reads the updated location-preference frontend doc
- **THEN** the doc states that popup is shown only for pending offers and lists accept, decline, and already-saved/suppressed skip paths
