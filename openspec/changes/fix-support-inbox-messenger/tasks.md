# Tasks

## 1. Backend model, ordering, and empty filter

- [x] 1.1 Add nullable `last_message_sender` on `SupportConversation`, set it in `post_message` with last-message updates, and add a migration; verify migrate applies cleanly on the project DB
- [x] 1.2 Change `apply_admin_conversation_filters` and `SupportConversation.Meta.ordering` to `F('last_message_at').desc(nulls_last=True), '-id'`, replace the matching index in the same migration, and verify SQL/ordering intent in migration operations
- [x] 1.3 Default-filter `last_message_at__isnull=False` unless `include_empty=true`; allowlist `include_empty` on `AdminSupportConversationViewSet.get_queryset`; verify unknown params still `400` and `include_empty` is accepted
- [x] 1.4 Expose `last_message_sender` on `AdminConversationListSerializer` (and detail inheritance); verify serializer field appears in list responses in tests

## 2. Backend inbox WebSocket and summary payload

- [x] 2.1 Extend `serialize_conversation_summary` with `last_message_sender` and `customer.profile_picture_url`; verify payload shape in unit/service tests
- [x] 2.2 Add `SupportAdminInboxConsumer` + route `ws/support/inbox/` (verified admin only, close `4403` otherwise, join `ADMIN_INBOX_GROUP`, forward `support.event`); leave per-conversation consumer behavior intact; verify non-admin rejected and admin accepted in consumer tests
- [x] 2.3 Confirm REST and WS `post_message` paths call `broadcast_admin_inbox('conversation.updated', ...)`; add/adjust a test that an inbox-only admin receives `conversation.updated` after a customer message
- [x] 2.4 Add API tests: NULL `last_message_at` never before messaged threads; default list excludes empties; `include_empty=true` includes empties at end; `last_message_sender` after customer then admin; run `support/tests/` relevant suite and verify pass

## 3. Backend docs and OpenAPI

- [x] 3.1 Update admin list OpenAPI parameters/examples for `include_empty` and `last_message_sender`; verify spectacular schema includes them
- [x] 3.2 Update `support/docs/frontend/support-inbox.md` (and backend ops note if needed) for ordering, empty default, inbox WS URL, and summary fields; verify docs match implemented contract

## 4. Frontend ordering, types, and infinite list (`befood-frontend`)

- [x] 4.1 Align `compareByRecency` with server (nulls last, id/`public_id` DESC) and extend `supportInboxTypes` for `last_message_sender`; verify `supportInboxMappers.test.ts` covers parity cases
- [x] 4.2 Switch admin inbox list data loading to TanStack `useInfiniteQuery` + IntersectionObserver bottom sentinel; remove `page` from URL params while keeping status/`q`/unread/`c`; verify scroll loads next page and URL has no `page`
- [x] 4.3 Implement move-to-top cache helper for infinite pages (remove from all pages, prepend page 0, count hygiene); verify unit tests for upsert/move-to-top across multi-page cache

## 5. Frontend inbox realtime and chrome (`befood-frontend`)

- [x] 5.1 Add page-level `useAdminSupportInboxRealtime` to `ws/support/inbox/` (token via existing WS URL builder, no URL logging, reconnect backoff); wire `conversation.updated` to move-to-top without unread bump when that conversation is open; verify polling runs only while inbox socket disconnected
- [x] 5.2 Implement scroll UX (animate at top; floating “New messages” when scrolled down), tab title unread total, optional notification sound with muted preference in `localStorage` (try/catch); verify title updates on open/clear unread
- [x] 5.3 Restyle list/filters to Messenger-like rows (avatar+online overlay, You: prefix, typing, unread badge, status badge rules, sticky search + All|Unread pills, empty state); keep mobile list↔chat toggle and a11y; verify visually and that per-conversation chat send/read/typing/presence still works
- [x] 5.4 Run frontend vitest for touched modules plus lint/typecheck; verify all pass

## 6. Integration acceptance

- [ ] 6.1 End-to-end smoke: new customer message appears at inbox position #1 within ~1s with only inbox WS connected; empty threads absent by default; refetch does not reshuffle vs client order; open conversation clears unread + title; verify against acceptance criteria checklist
