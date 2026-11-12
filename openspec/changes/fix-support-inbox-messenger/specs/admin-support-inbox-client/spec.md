# Spec Delta

## Purpose

Defines Admin Support Inbox web client behavior so the list looks and updates like Messenger: recency ordering parity with the API, live move-to-top, infinite scroll, and clear unread affordances.

## ADDED Requirements

### Requirement: Client ordering matches server recency

The admin inbox client MUST sort conversations by `last_message_at` descending with null timestamps last, then by descending conversation id/`public_id` as tie-breaker, matching the admin list API. Client-side upserts and refetch merges MUST preserve this order so the list does not reshuffle relative to the server.

#### Scenario: Null last_message_at sorts after real messages

- **WHEN** the client sorts a mix of conversations with and without `last_message_at`
- **THEN** conversations with null `last_message_at` MUST appear after all conversations that have a timestamp

#### Scenario: Unit tests cover compareByRecency parity

- **WHEN** the client unit tests for the inbox mapper sorter run
- **THEN** they MUST assert newest-first ordering, nulls-last behavior, and stable id/`public_id` tie-break

### Requirement: Infinite scroll conversation list

The admin inbox list MUST load conversations with infinite scroll (next page when the list bottom enters view) instead of Prev/Next page controls. URL state MUST keep filters such as status, `q`, unread, and selected conversation `c`, and MUST NOT require a `page` query param for normal browsing.

#### Scenario: Scroll loads next page

- **WHEN** the admin scrolls the conversation list so the bottom sentinel enters the viewport and more pages exist
- **THEN** the client MUST request the next page and append results without a full page reload

### Requirement: Page-level inbox realtime connection

While the Admin Support Inbox page is open, the client MUST maintain a WebSocket to `/ws/support/inbox/` authenticated with the admin token. On `conversation.updated`, the client MUST remove that conversation from all cached infinite-query pages and prepend it to the first page (move-to-top), including conversations not previously in cache. If that conversation is currently open, the client MUST NOT increment its unread affordance as if newly unread. List polling MUST run only while the inbox socket is disconnected and MUST NOT depend solely on the per-conversation chat socket connected flag. Auto-reconnect with backoff MUST be used. Connection URLs MUST NOT be logged.

#### Scenario: New customer message moves thread to top without open chat

- **WHEN** a `conversation.updated` arrives for a customer message while no conversation chat socket is required for inbox updates
- **THEN** that conversation MUST appear at the top of the cached list within about one second without a full page refresh

#### Scenario: Open conversation does not bump unread on self-read update

- **WHEN** `conversation.updated` arrives for the conversation the admin currently has open
- **THEN** the client MUST still move/update the row but MUST NOT treat it as a new unread increase for that open thread

#### Scenario: Polling only when inbox socket down

- **WHEN** the inbox WebSocket is disconnected
- **THEN** the client MAY poll the conversation list on a short interval as fallback
- **AND WHEN** the inbox WebSocket is connected
- **THEN** that polling fallback MUST be disabled

### Requirement: Scroll UX for incoming updates

If the admin list scroll position is at the top, newly prepended conversations MUST appear at the top with a smooth enter animation. If the admin has scrolled down, the list MUST NOT jump; the UI MUST show a floating control (e.g. “New messages”) that scrolls to the top when activated.

#### Scenario: Scrolled-down admin sees new-messages pill

- **WHEN** a conversation is prepended while the list is scrolled away from the top
- **THEN** a floating new-messages control MUST appear and activating it MUST scroll to the top

### Requirement: Unread tab title and optional sound

The browser tab title MUST reflect total admin unread across the inbox (e.g. `(3) Support Inbox`). The client MAY play a short notification sound on a new customer message and MUST respect a mute preference stored in `localStorage` (access wrapped so storage failures do not break the page).

#### Scenario: Tab title shows unread total

- **WHEN** the inbox has a non-zero aggregate admin unread count
- **THEN** the document title MUST include that count
- **AND WHEN** the admin opens a conversation and clears its unread
- **THEN** the title count MUST update accordingly

### Requirement: Messenger-style list presentation

Conversation rows MUST present a Messenger-like layout: 48px avatar with online indicator overlaid bottom-right; name emphasized when unread with relative time on the right; single-line truncated preview prefixed with `You: ` when `last_message_sender` is `admin`; unread preview stronger than read; typing indicator in brand color when a typing event is active for that row; unread dot or count badge; status badge hidden for `open` and subtle only for `closed`/`archived`; selected/hover row styling with rounded rows; sticky header with rounded search and All | Unread pill tabs (status filter in a compact overflow/menu); friendly empty state when no conversations. Existing mobile list↔chat toggle and accessibility affordances MUST be preserved.

#### Scenario: Unread row shows You prefix for admin last message

- **WHEN** a conversation’s `last_message_sender` is `admin` and it appears in the list
- **THEN** the preview line MUST be prefixed with `You: `

#### Scenario: Empty inbox friendly state

- **WHEN** the filtered inbox has zero conversations
- **THEN** the client MUST show a friendly empty state indicating no messages yet

### Requirement: No regression in per-conversation chat

Per-conversation send, read receipts, typing, and presence MUST continue to work while inbox-level realtime and list UX changes are active.

#### Scenario: Open chat still exchanges messages

- **WHEN** an admin has a conversation open and exchanges messages with the customer
- **THEN** send, read receipts, typing, and presence MUST continue to function without requiring a page refresh
