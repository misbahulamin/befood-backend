# Delivery Man auth & admin management (frontend)

## Summary

Delivery Man app: register → verify email → wait for admin → login.  
Admin panel: pending list → detail → approve / reject / revoke.

Base prefix: `/user_management/`  
Auth header after login: `Authorization: Token <token>`

Bangla pending copy can be rendered in the UI; the API returns English `detail`.

---

## Delivery Man — auth flow

### 1. Register

`POST /user_management/deliveryman/register/`

```json
{
  "email": "rider@example.com",
  "first_name": "Karim",
  "last_name": "Hossain",
  "phone": "1812345678",
  "address": "House 10, Road 2, Dhaka",
  "password": "StrongPassword123",
  "vehicle_type": "bike",
  "license_number": ""
}
```

`vehicle_type` / `license_number` optional.

**201**

```json
{
  "message": "Registration successful. Please check your email to verify your account.",
  "email": "rider@example.com"
}
```

Show: “Check your email to verify.”

### 2. Email verification

User opens link from email:

`GET /user_management/deliveryman/verify-email/<uidb64>/<token>/`

**200** — email verified; still **cannot** login until admin approves.

UI state after verify: “Waiting for admin approval.”

### 3. Resend verification

`POST /user_management/deliveryman/resend-verification/`

```json
{ "email": "rider@example.com" }
```

### 4. Login

`POST /user_management/deliveryman/login/`

```json
{
  "email": "rider@example.com",
  "password": "StrongPassword123"
}
```

**200 success**

```json
{
  "token": "...",
  "user": {
    "id": 1,
    "email": "rider@example.com",
    "first_name": "Karim",
    "last_name": "Hossain"
  },
  "groups": ["DELIVERY_MAN"],
  "rider_profile": {
    "public_id": "…",
    "phone": "1812345678",
    "address": "House 10, Road 2, Dhaka",
    "vehicle_type": "bike",
    "license_number": "",
    "is_email_verified": true,
    "approval_status": "approved",
    "is_verified": true,
    "is_available": true
  }
}
```

**400 — not approved yet** (email verified, admin pending/rejected)

```json
{
  "detail": "Your information has not been approved by admin yet. Please wait until your account verification is completed."
}
```

Suggested BN UI string:

> আপনার তথ্য এখনো Admin Panel থেকে approve করা হয়নি। Approval সম্পন্ন হলে আপনি login করতে পারবেন।

**400 — email not verified**

```json
{ "detail": "Please verify your email before login." }
```

**400 — bad password**

```json
{ "detail": "Invalid credentials." }
```

### 5. Current user

`GET /user_management/deliveryman/me/`  
Header: `Authorization: Token <token>`

Only approved Delivery Men.

---

## Admin panel — Delivery Man management

Requires verified admin token (`POST /user_management/admin/login/` first).

### Pending list (default)

`GET /user_management/admin/deliverymen/`

Default = email verified + `approval_status=pending`.

Query options:

| Param | Meaning |
|-------|---------|
| `pending_only=false` | Disable default pending filter |
| `approval_status=approved\|rejected\|pending` | Explicit status |
| `is_email_verified=true\|false` | Email filter |
| `is_verified=true\|false` | Verified flag |
| `search=` | Email / name / phone |
| `page`, `page_size` | Pagination (default 20, max 100) |

Use `public_id` from each row for detail/actions (never integer PK).

### Detail

`GET /user_management/admin/deliverymen/<public_id>/`

Shows name, email, phone, address, verification & approval fields, notes.

### Approve

`POST /user_management/admin/deliverymen/<public_id>/approve/`  
Body empty.

Sends approval email; rider can login afterward.

### Reject

`POST /user_management/admin/deliverymen/<public_id>/reject/`

```json
{ "reason": "Incomplete documents" }
```

`reason` optional.

### Verified status (revoke / re-approve)

`PATCH /user_management/admin/deliverymen/<public_id>/verified-status/`

```json
{ "is_verified": false, "admin_notes": "Suspended" }
```

```json
{ "is_verified": true }
```

---

## UI state checklist

| State | Delivery Man UI | Admin UI |
|-------|-----------------|----------|
| Just registered | “Verify email” | Not in pending queue |
| Email verified | “Waiting for approval” | In pending list |
| Approved | Can login / home | Status approved |
| Rejected | Login shows pending message | Status rejected |
| Revoked | Login blocked again | `is_verified=false` |

## Target clients

- Delivery Man: mobile and/or web
- Admin management: web
