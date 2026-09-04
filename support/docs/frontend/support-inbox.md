# Support Inbox — Mobile & Admin Frontend Integration

This document explains how to integrate BeFood **customer support live chat** for:

1. **Mobile app** (customer)
2. **Admin web panel** (verified admin)

You do **not** need prior knowledge of the backend. Follow the flows in order.

---

## 1. What is this feature?

Each customer has **one permanent Support Conversation** (inbox).

- Customer sends text messages from the mobile app.
- Admin replies from the web Support Inbox.
- Messages are saved forever (no delete API).
- **REST** loads history (and works as fallback send).
- **WebSocket** delivers messages, typing, and online status instantly (no page refresh).
- If the other side is **offline**, the system uses existing **FCM** (customer) or **admin email** (ops).

Out of scope for v1: images, files, voice, video, canned replies.

---

## 2. Auth (both clients)

| Item | Value |
|------|--------|
| Header | `Authorization: Token <your_token>` |
| Customer login | Existing customer login → Token |
| Admin login | Existing admin login → Token |
| Optional | `X-Client-Type: mobile` or `web` (not required for these endpoints) |

WebSocket auth (recommended):

```text
wss://<api-host>/ws/support/<conversation_public_id>/?token=<your_token>
```

HTTPS/WSS only in production. Do not log the full token.

---

## 3. Endpoint grid

### Customer (mobile)

| Step | Method | Path | Why |
|------|--------|------|-----|
| 1 | `GET` | `/api/v1/support/inbox/` | Load conversation + paginated history; marks customer-side messages read |
| 2 | `POST` | `/api/v1/support/messages/` | Fallback send if WebSocket is down |
| 3 | `WS` | `/ws/support/{conversation_public_id}/` | Live send/receive, typing, presence |

### Admin (web panel)

| Step | Method | Path | Why |
|------|--------|------|-----|
| 1 | `GET` | `/api/v1/web/support/conversations/` | Left-pane conversation list |
| 2 | `GET` | `/api/v1/web/support/conversations/{public_id}/` | Open chat + history; clears admin unread |
| 3 | `POST` | `/api/v1/web/support/conversations/{public_id}/reply/` | REST reply fallback |
| 4 | `PATCH` | `/api/v1/web/support/conversations/{public_id}/status/` | Set `open` / `closed` / `archived` |
| 5 | `WS` | `/ws/support/{conversation_public_id}/` | Live chat for selected thread |

---

## 4. Recommended mobile workflow

```text
App open Support screen
  → GET /api/v1/support/inbox/
  → Read conversation.public_id
  → Connect WebSocket with token
  → Render messages[] oldest → newest
  → On send: prefer WS message.send; if WS disconnected use POST /messages/
  → Show typing / agent online from WS events
  → On FCM type=support_reply: deep-link to Support screen and refresh
```

### 4.1 `GET /api/v1/support/inbox/`

**Permission:** authenticated user with `CustomerProfile`.

**Query**

| Param | Default | Max | Meaning |
|-------|---------|-----|---------|
| `page` | 1 | — | Page number |
| `page_size` | 50 | 100 | Messages per page |

**Success `200` example**

```json
{
  "conversation": {
    "public_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "status": "open",
    "last_message": "Lunch missing",
    "last_message_at": "2026-09-04T08:00:00+06:00",
    "customer_unread_count": 0,
    "created_at": "2026-09-04T07:00:00+06:00",
    "updated_at": "2026-09-04T08:00:00+06:00",
    "support_agent_online": true
  },
  "messages": [
    {
      "public_id": "…",
      "sender_type": "customer",
      "body": "Lunch missing",
      "is_read_by_customer": true,
      "is_read_by_admin": false,
      "created_at": "2026-09-04T08:00:00+06:00"
    }
  ],
  "pagination": {
    "count": 1,
    "next": null,
    "previous": null,
    "page_size": 50
  }
}
```

**Field meanings**

| Field | Meaning |
|-------|---------|
| `conversation.public_id` | Stable inbox id — use in WebSocket URL |
| `status` | `open` \| `closed` \| `archived` |
| `customer_unread_count` | Unread admin/system messages for this customer (cleared on this GET) |
| `support_agent_online` | Soft signal: any admin currently connected to support |
| `sender_type` | `customer` \| `admin` \| `system` |
| `body` | Plain text message |

**Errors:** `401` unauthenticated, `403` no customer profile.

### 4.2 `POST /api/v1/support/messages/`

**Body (either key works)**

```json
{ "message": "আমার delivery সমস্যা হচ্ছে" }
```

**Success `201`**

```json
{
  "public_id": "…",
  "sender_type": "customer",
  "body": "আমার delivery সমস্যা হচ্ছে",
  "is_read_by_customer": true,
  "is_read_by_admin": false,
  "created_at": "…"
}
```

**Errors:** `400` empty message, `401`, `403`.

Prefer WebSocket `message.send` when connected; use this POST only as fallback so admin still gets the message + offline email if needed.

### 4.3 Mobile WebSocket events

Connect:

```text
wss://api.example.com/ws/support/3fa85f64-5717-4562-b3fc-2c963f66afa6/?token=YOUR_TOKEN
```

**Client → server**

```json
{ "type": "message.send", "payload": { "message": "Hello" } }
{ "type": "typing.start", "payload": {} }
{ "type": "typing.stop", "payload": {} }
{ "type": "message.read", "payload": {} }
{ "type": "presence.ping", "payload": {} }
```

**Server → client**

```json
{ "type": "message.receive", "payload": { "public_id": "…", "sender_type": "admin", "body": "…", "created_at": "…" } }
{ "type": "typing.start", "payload": { "role": "admin", "user_id": 12 } }
{ "type": "typing.stop", "payload": { "role": "admin", "user_id": 12 } }
{ "type": "presence.online", "payload": { "role": "admin", "user_id": 12 } }
{ "type": "presence.offline", "payload": { "role": "admin", "user_id": 12 } }
{ "type": "message.read", "payload": { "reader": "admin", "admin_unread_count": 0 } }
{ "type": "error", "payload": { "detail": "…" } }
```

**UI mapping**

| Event | UI |
|-------|-----|
| `message.receive` | Append bubble; if `sender_type=admin` show as support |
| `typing.start` (role=admin) | Show “Support is typing…” |
| `typing.stop` | Hide typing |
| `presence.online` (role=admin) | Green “Support online” |
| `presence.offline` | Offline / away |
| Close `4401` | Re-login |
| Close `4403` / `4404` | Wrong conversation — reload inbox |

Send `presence.ping` every ~30s while the chat screen is open (keeps Redis TTL warm).

### 4.4 FCM (offline customer)

When admin replies and the customer is **not** on the WebSocket:

| Key | Example |
|-----|---------|
| Notification title | `BeFood Support` |
| Body | `আপনার message এর reply এসেছে` |
| `data.type` | `support_reply` |
| `data.screen` | `support_inbox` |
| `data.conversation_public_id` | UUID string |
| `data.message_public_id` | UUID string |

Also stored in existing `/notifications/inbox/` feed.

---

## 5. Recommended admin web workflow

```text
Open Support Inbox page
  → GET /api/v1/web/support/conversations/?page=1
  → Render left list (name, phone, email, last message, unread, online)
  → On row click:
       GET .../conversations/{public_id}/
       Connect WS for that public_id
  → Chat pane: history + live events
  → Send: WS message.send (or POST .../reply/ fallback)
  → Optional: PATCH .../status/ { "status": "closed" }
```

### 5.1 UI layout (suggested)

**Left pane — conversation list**

- Customer name, phone, email  
- Last message + time  
- Unread badge (`admin_unread_count`)  
- Online dot (`customer_online`)  
- Status chip (`open` / `closed` / `archived`)

**Right pane — chat**

- Message history (customer vs admin bubbles)  
- Typing indicator  
- Composer  
- Status dropdown  

### 5.2 `GET /api/v1/web/support/conversations/`

**Permission:** verified admin (`IsVerifiedAdmin`).

**Query filters (allowlisted)**

| Param | Example | Meaning |
|-------|---------|---------|
| `status` | `open` | Filter by status |
| `has_unread` | `true` | `admin_unread_count > 0` |
| `q` | `rahim` | Search name / phone / email / last message |
| `page` | `1` | Page |
| `page_size` | `20` (max 100) | Page size |

Unknown filters → `400`.

**List item fields**

| Field | Meaning |
|-------|---------|
| `public_id` | Conversation id for detail + WS |
| `customer_name` / `phone` / `email` | Identity |
| `customer_public_id` | Link to customer 360 if needed |
| `last_message` / `last_message_at` | Preview |
| `admin_unread_count` | Badge |
| `customer_online` | Soft presence from cache |
| `status` | open/closed/archived |

### 5.3 `GET /api/v1/web/support/conversations/{public_id}/`

Returns:

```json
{
  "conversation": { "...": "..." },
  "messages": [ ... ],
  "pagination": { "count": 12, "next": null, "previous": null, "page_size": 50 }
}
```

Opening detail **clears admin unread** for that thread.

### 5.4 `POST .../reply/`

```json
{ "message": "আমরা বিষয়টি দেখছি" }
```

→ `201` message object. Prefer WS when connected.

### 5.5 `PATCH .../status/`

```json
{ "status": "closed" }
```

Allowed: `open`, `closed`, `archived`.

### 5.6 Admin WebSocket

Same URL and event contract as mobile. Admin may join **any** conversation. On connect, admin also joins an internal inbox group and may receive:

```json
{ "type": "conversation.updated", "payload": { "public_id": "…", "last_message": "…", "admin_unread_count": 1, "customer": { ... } } }
```

Use this to bump the left list without polling.

---

## 6. Permissions matrix

| Actor | Customer REST | Admin REST | Own conversation WS | Other customer WS |
|-------|---------------|------------|---------------------|-------------------|
| Anonymous | 401 | 401 | close 4401 | close 4401 |
| Customer | yes | 403 | yes | close 4403 |
| Verified admin | n/a (use admin APIs) | yes | yes | yes |
| Non-verified staff | — | 403 | — | — |

---

## 7. Message rules (both UIs)

1. Never offer a Delete message button (API does not support it).  
2. Render `sender_type=system` as system notices if present.  
3. Order messages by `created_at` ascending.  
4. One conversation per customer — do not create multiple threads in UI.  
5. Typing is ephemeral — never save as a message bubble.

---

## 8. Error cheat sheet

| HTTP / WS | Meaning | Client action |
|-----------|---------|---------------|
| `401` | Missing/invalid token | Re-login |
| `403` | Wrong role | Hide feature |
| `400` / `422` | Validation (empty message, bad filter) | Show field error |
| `404` | Unknown conversation (admin) | Refresh list |
| WS `4401` | Auth failed | Re-login, reconnect |
| WS `4403` | Forbidden conversation | Reload inbox public_id |
| WS `4404` | Conversation missing | Call GET inbox again |

---

## 9. Quick checklist

**Mobile**

- [ ] Token on REST + WS query  
- [ ] Load inbox before connecting WS  
- [ ] Prefer WS send; REST fallback  
- [ ] Handle FCM `support_reply` → open Support  
- [ ] Typing + online indicators  

**Admin**

- [ ] List with filters/search  
- [ ] Detail clears unread  
- [ ] Live WS for open thread  
- [ ] Status patch  
- [ ] Left list updates on `conversation.updated`  

---

## 10. How to verify quickly

1. Customer Token → `POST /api/v1/support/messages/` with a message.  
2. Admin Token → list shows the conversation with unread.  
3. Open two WS clients (customer + admin); send; confirm `message.receive`.  
4. Send `typing.start`; peer sees typing; no new DB message.  
5. Disconnect customer WS; admin replies via REST; customer gets FCM/inbox alert.

Automated: `python manage.py test support.tests`.

Related backend ops notes: `support/docs/backend/support-inbox-ops.md`.
