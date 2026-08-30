# Frontend: Customer Profile Picture

## Summary

Customers upload a profile picture from the account profile page. The backend stores the file via Django default media storage (AWS S3 when `USE_S3_MEDIA=true`) and returns a URL the UI can display.

**Target client:** Customer web SPA (`/account/profile`).

## Auth

```http
Authorization: Token <customer-token>
```

Requires an authenticated user with a `customer_profile`. Non-customers are denied.

## Upload

```http
POST /api/v1/user_management/customer/profile/image/
Content-Type: multipart/form-data
```

| Form field | Required | Notes |
|------------|----------|--------|
| `image` | Yes | File: jpg / jpeg / png / webp, max **2 MB** |

### Success (`200`)

```json
{
  "profile_image_url": "https://…/profiles/users/abdul_rahim_a1b2c3d4/profile_picture.jpg",
  "message": "Profile picture updated."
}
```

When S3 is enabled the URL is an absolute HTTPS object URL. Locally (S3 off) it may be a `/media/...` path absolutized by the API.

### Errors

| Status | When |
|--------|------|
| `401` | Missing/invalid token |
| `403` | Authenticated but no customer profile |
| `400` | Missing file, invalid extension, or size &gt; 2 MB |

Example validation body:

```json
{
  "image": ["Invalid image extension. Allowed extensions: jpg, jpeg, png, webp."]
}
```

## Read URL on profile

```http
GET /api/v1/user_management/customer/profile/
```

`profile_image_url` appears:

- Top-level on the extended profile response
- Under `customer_profile.profile_image_url`

Value is `null` when no picture is stored.

## Clear picture

```http
PATCH /api/v1/user_management/customer/profile/
Content-Type: application/json

{ "profile_image_url": null }
```

Only explicit `null` clears the stored file. Sending a data URL or remote URL is **ignored** (upload must use the dedicated POST endpoint).

## Integration steps

1. Validate file client-side (type + ≤ 2 MB) before upload.
2. `POST` multipart with field name exactly `image`.
3. On success, show `profile_image_url` (or invalidate extended profile query).
4. On remove, `PATCH` with `profile_image_url: null`, then refresh profile.

## Edge cases

- Replacing a picture deletes the previous media object when feasible.
- Folder keys are name/email-based with a short `public_id` suffix for uniqueness.
