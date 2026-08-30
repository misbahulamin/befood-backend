# Backend: Customer Profile Picture

## Quick summary

| Item | Detail |
|------|--------|
| Model field | `CustomerProfile.profile_picture` (`ImageField`) |
| Upload | `POST /api/v1/user_management/customer/profile/image/` |
| Clear | `PATCH .../customer/profile/` with `profile_image_url: null` |
| Permission | `HasCustomerProfile` (owner only) |
| Storage | Django default media backend |

## Object key layout

```text
profiles/users/{folder_slug}/profile_picture.{ext}
```

`{folder_slug}` = `{sanitized_name_or_email_local}_{public_id8}`

1. Prefer `first_name` + `last_name` → lowercase, spaces → `_`, non-alnum stripped/collapsed
2. Else email local-part before `@`
3. Fallback base `user`
4. Always append first 8 hex chars of customer `public_id` (no dashes)

Examples:

- Name `Abdul Rahim` → `profiles/users/abdul_rahim_<id8>/profile_picture.jpg`
- Email `rahim123@gmail.com` (no name) → `profiles/users/rahim123_<id8>/profile_picture.png`

## Validation

| Rule | Value |
|------|--------|
| Extensions | `jpg`, `jpeg`, `png`, `webp` |
| Max size | 2 MiB |

Implemented in `user_management/services/profile_picture.py`.

## S3 / production

Media goes through the existing `USE_S3_MEDIA` toggle (`core.storage.S3MediaStorage`).

**Production requirement for durable profile pictures:**

- `USE_S3_MEDIA=true`
- `AWS_STORAGE_BUCKET_NAME` and `AWS_S3_REGION_NAME` set
- IAM role or access keys with Put/Get/Delete/List on the media bucket

When `USE_S3_MEDIA=false` (local default), files land under `MEDIA_ROOT` — fine for development, not production behaviour.

See also: `core/docs/backend/s3-media-storage.md`.

## Replace / clear

- **Replace:** save new file, then best-effort `default_storage.delete(old_name)`
- **Clear:** null the field, delete previous storage object
- Service entry points: `upload_profile_picture`, `clear_profile_picture`, `get_profile_picture_url`

## Admin directory

List and overview `profile_picture_url` return the stored media URL (or `null`), not a hardcoded null.

## How to verify

1. Authenticated customer POST a JPEG as `image` → `200` + `profile_image_url`
2. GET extended profile → same URL under `customer_profile.profile_image_url`
3. With `USE_S3_MEDIA=true`, confirm object in the S3 console under `profiles/users/...`
4. Upload again → old object removed / no longer referenced
5. PATCH `{ "profile_image_url": null }` → URL becomes null
6. Automated: `user_management/tests/test_customer_profile_picture.py`
