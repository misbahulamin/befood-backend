## Why

The customer Profile page (`/account/profile`) already uploads a profile picture via `POST /user_management/customer/profile/image/`, but the backend never implemented that endpoint and removed the old `CustomerProfile.avatar` field. Uploads return 404; the frontend falls back to a local data-URL preview, so nothing is persisted to AWS S3. Users expect a durable S3-backed profile image after registration/login.

## What Changes

- Restore a profile picture field on `CustomerProfile` (ImageField) with a scalable S3 object-key layout under `profiles/users/...`
- Add `POST /user_management/customer/profile/image/` matching the existing frontend contract (`multipart` field `image` → `profile_image_url`)
- Return `profile_image_url` on customer extended profile GET/PATCH responses
- Wire uploads through existing django-storages / `USE_S3_MEDIA` S3 media backend (no new upload stack)
- Validate image type (jpg/jpeg/png/webp) and size; reject invalid files
- Replace flow: delete or replace the previous S3 object when a new picture is uploaded
- Enforce ownership: only the authenticated customer can update their own picture
- Update admin customer directory `profile_picture_url` to return the real S3/media URL when present (was always `null`)
- Add backend + frontend docs and automated tests for path naming, validation, replace, and auth

## Capabilities

### New Capabilities
- `customer-profile-picture`: Authenticated customer profile picture upload, storage path/filename rules, validation, replace/delete handling, and `profile_image_url` exposure on the customer profile API

### Modified Capabilities
- `admin-customer-directory`: `profile_picture_url` MUST return the stored media URL when a profile picture exists (instead of always `null`)

## Impact

- **Models:** `user_management.CustomerProfile` — add ImageField + migration
- **API:** new upload endpoint; extended profile serializers/views; admin customer serializers/services
- **Storage:** reuse `core.storage.S3MediaStorage` when `USE_S3_MEDIA=true`; object keys under `profiles/users/{identifier}/`
- **Frontend:** no required contract change — already calls the upload URL and reads `profile_image_url`
- **Deps:** none new (`django-storages` / `boto3` already present)
- **Ops:** production must have `USE_S3_MEDIA=true` and valid AWS bucket/region (and credentials or IAM role) for S3 persistence
