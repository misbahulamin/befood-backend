# Admin Authentication API

## 1. Feature overview

Admin accounts are **not** created through a public API. A superuser creates and verifies admin accounts from the **Django admin panel**.

The frontend admin app uses a dedicated login endpoint:

- `POST /user_management/admin/login/`

Only **verified admin accounts** can log in through this endpoint. After login, the admin receives a token and can access all protected admin/manager APIs.

**Authentication:** Token auth (`Authorization: Token <token>`)

**Base prefix:** `/user_management/`

---

## 2. How admin accounts are created (backend team / Django admin)

Admin registration is handled only in Django admin. No frontend registration form is required.

### Step 1: Create a Django user

In Django admin, go to **Users** and create a user with:

- unique `username`
- valid `email`
- strong `password`
- optional `first_name` / `last_name`

Do **not** enable login yet unless you also verify the admin profile in step 2.

### Step 2: Create an Admin Profile

In Django admin, go to **Admin profiles** and create a record:

| Field | Required | Notes |
| --- | --- | --- |
| `user` | Yes | Select the user created in step 1 |
| `is_verified` | Yes | Must be `true` before API login works |
| `notes` | No | Internal notes only |

When you save an admin profile:

- the user is automatically added to the `ADMIN` group
- `verified_at` is set automatically when `is_verified=true`
- `user.is_active` is synced with `is_verified`

### Important rules

- Unverified admins **cannot** log in through the admin login API.
- Customer accounts **cannot** use the admin login endpoint.
- Superusers can log in through the admin login endpoint even without an `AdminProfile`.

---

## 3. Admin login

### Endpoint

`POST /user_management/admin/login/`

### Request body

```json
{
  "email": "admin@example.com",
  "password": "StrongPassword123"
}
```

| Field | Type | Required |
| --- | --- | --- |
| `email` | string (email) | Yes |
| `password` | string | Yes |

### Success response `200`

```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": {
    "id": 3,
    "email": "admin@example.com",
    "first_name": "Admin",
    "last_name": "User",
    "is_superuser": false
  },
  "groups": ["ADMIN"],
  "is_admin": true,
  "admin_profile": {
    "is_verified": true,
    "verified_at": "2026-07-10T12:00:00Z"
  }
}
```

### Error responses `400`

| Message | Meaning |
| --- | --- |
| `Invalid credentials.` | Wrong email or password |
| `Account is inactive.` | User account is inactive |
| `Admin account is not verified yet.` | Admin profile exists but is not verified |
| `This account is not authorized for admin login.` | User is not an admin account |

### Frontend notes

- Store the returned `token` securely.
- Send it on every protected request:

```http
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

- Use the **admin login page only** for admin users.
- Do **not** use the customer login endpoint (`POST /user_management/login/`) for admin users.

---

## 4. Get current admin user

### Endpoint

`GET /user_management/admin/me/`

### Headers

```http
Authorization: Token <token>
```

### Success response `200`

```json
{
  "user": {
    "id": 3,
    "email": "admin@example.com",
    "first_name": "Admin",
    "last_name": "User",
    "is_superuser": false
  },
  "groups": ["ADMIN"],
  "admin_profile": {
    "is_verified": true,
    "verified_at": "2026-07-10T12:00:00Z"
  },
  "is_admin": true,
  "is_authenticated": true
}
```

### Error responses

| Status | Meaning |
| --- | --- |
| `401` | Missing or invalid token |
| `403` | Token belongs to a non-admin user |

Use this endpoint on admin app startup to restore session state.

---

## 5. Logout

Admins use the same logout endpoint as other authenticated users.

### Endpoint

`POST /user_management/logout/`

### Headers

```http
Authorization: Token <token>
```

### Success response `200`

```json
{
  "message": "Logged out successfully."
}
```

After logout, delete the stored token on the frontend.

---

## 6. Admin access rules

Verified admins have **full access** to protected manager/admin APIs, including:

- meal create/update/delete
- order management endpoints that require manager/admin permission
- other endpoints guarded by group-based permissions

Access logic:

- verified admin (`ADMIN` group + verified `AdminProfile`) => full access
- superuser => full access
- customer token => customer-only endpoints only

If an admin receives `403 Forbidden` on a protected endpoint, verify:

1. login was done through `/user_management/admin/login/`
2. token is sent correctly in the `Authorization` header
3. admin account is verified in Django admin

---

## 7. Recommended frontend flow

```mermaid
sequenceDiagram
    participant AdminApp
    participant API

    AdminApp->>API: POST /user_management/admin/login/
    API-->>AdminApp: token + admin user data
    AdminApp->>AdminApp: save token
    AdminApp->>API: GET /user_management/admin/me/
    API-->>AdminApp: current admin session
    AdminApp->>API: protected admin APIs with Authorization header
    AdminApp->>API: POST /user_management/logout/
    API-->>AdminApp: logged out
    AdminApp->>AdminApp: clear token
```

---

## 8. Example frontend integration

### Login

```javascript
const response = await fetch('/user_management/admin/login/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'admin@example.com',
    password: 'StrongPassword123',
  }),
});

const data = await response.json();

if (!response.ok) {
  throw new Error(data.detail || 'Admin login failed');
}

localStorage.setItem('adminToken', data.token);
```

### Authenticated request

```javascript
const token = localStorage.getItem('adminToken');

const response = await fetch('/meals/', {
  headers: {
    Authorization: `Token ${token}`,
  },
});
```

### Session restore

```javascript
const token = localStorage.getItem('adminToken');

const response = await fetch('/user_management/admin/me/', {
  headers: {
    Authorization: `Token ${token}`,
  },
});

if (response.status === 401 || response.status === 403) {
  localStorage.removeItem('adminToken');
}
```

---

## 9. Customer vs admin auth comparison

| Item | Customer | Admin |
| --- | --- | --- |
| Registration API | Yes (`POST /user_management/customer/register/`) | No |
| Account creation | Self-service + email verification | Django admin panel only |
| Login endpoint | `POST /user_management/login/` | `POST /user_management/admin/login/` |
| Verification requirement | Email verification | Manual admin verification |
| Current user endpoint | `GET /user_management/me/` | `GET /user_management/admin/me/` |
| Logout endpoint | `POST /user_management/logout/` | Same |
| Access scope | Customer APIs | Full admin/manager APIs |

---

## 10. Swagger / OpenAPI

Interactive docs are available at:

- Swagger UI: `/api/docs/`
- OpenAPI schema: `/api/schema/`

Look for the **Admin Auth** tag.
