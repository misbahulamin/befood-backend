## Context

Frontend (`befood-frontend`) Profile page already calls:

- `POST /user_management/customer/profile/image/` with `multipart/form-data` field `image`
- Expects `{ profile_image_url?: string; message?: string }`
- On `404`/`501`, falls back to a client-side data-URL preview via `PATCH` with `profile_image_url`

Backend today:

- No `customer/profile/image/` route (`user_management/api/urls.py`)
- `CustomerProfile` has no image field (`avatar` was removed in `0002_customer_auth_cleanup`)
- Admin APIs hardcode `profile_picture_url: null`
- S3 media infrastructure already exists (`USE_S3_MEDIA`, `core.storage.S3MediaStorage`, django-storages) from `setup-s3-media-storage`

Root cause is missing domain feature (field + endpoint + service), not a broken S3 driver. With `USE_S3_MEDIA=true`, any ImageField save uses S3; with `false`, files go to local `MEDIA_ROOT` (dev default).

Stakeholders: authenticated customers (upload), verified admins (read URL), ops (S3 env).

## Goals / Non-Goals

**Goals:**

- Persist profile pictures via Django ImageField through the default media storage (S3 when enabled)
- Match existing frontend upload API contract with minimal/no frontend change
- Scalable object-key layout: `profiles/users/{identifier}/profile_picture.{ext}`
- Name/email-based folder slug with collision safety
- Validate type/size; replace old object; owner-only updates
- Expose absolute media URL as `profile_image_url` / `profile_picture_url`

**Non-Goals:**

- New parallel upload microservice or direct browser→S3 signed-URL flow
- Cropping/CDN image transforms
- Deliveryman/staff/admin avatars
- Migrating historical local data-URL “previews” (never stored server-side)
- Changing static-file storage (WhiteNoise stays as-is)

## Decisions

### 1. Field on `CustomerProfile`, not a separate media table

- **Choice:** `profile_picture = models.ImageField(upload_to=..., blank=True, null=True)`
- **Why:** Matches meal/blog/announcement ImageField patterns; one active picture per customer; serializers/admin stay simple
- **Alternatives:** Separate `ProfileMedia` model (overkill for v1); restore name `avatar` (frontend already uses `profile_image_url`)

### 2. Endpoint + response shape = frontend contract

- **Choice:** `POST .../customer/profile/image/` accepting field `image`; response `{ "profile_image_url": "<absolute-or-media-url>", "message": "..." }` with `200`/`201`
- **Permissions:** `HasCustomerProfile` (same as profile GET/PATCH) — binds upload to `request.user.customer_profile`
- **Alternatives:** Nested action on profile viewset; PATCH multipart on profile (would diverge from frontend)

### 3. Upload path / filename service

- **Choice:** Reusable helpers in `user_management/services/profile_picture.py` (or `utils/`), mirroring `meals/services/meal_image.py`
- **Folder slug:**
  1. Prefer `User.get_full_name()` (or first+last) → lowercase, spaces→`_`, sanitize non-alnum to `_`, collapse repeats
  2. Else email local-part before `@`, same sanitization
  3. Fallback `user` if empty after sanitize
- **Object key:** `profiles/users/{folder_slug}_{public_id_hex8}/profile_picture.{ext}`
  - Readable name prefix + short `public_id` suffix avoids cross-user collisions at scale while staying close to the requested `profiles/users/john_doe/...` layout
- **Filename:** Always `profile_picture.{ext}` (ext from validated original)
- **Alternatives:** Folder = `public_id` only (less readable); exact `john_doe` without id (collision risk under millions of users)

### 4. Storage backend

- **Choice:** Rely on existing default storage; when `USE_S3_MEDIA=true`, ImageField.save → S3. No custom boto3 upload path for this feature
- **Overwrite:** `S3MediaStorage.file_overwrite = False` globally. On replace: delete previous file via `storage.delete(old.name)` before assigning the new file, then save. Prefer same logical key; if storage still uniquifies, store the returned name on the field
- **Production rule:** Document that profile pictures require `USE_S3_MEDIA=true` in prod; local disk only for local/dev when flag is false

### 5. Validation

- **Allowed extensions:** `jpg`, `jpeg`, `png`, `webp` (align with other media utils; frontend allows jpeg/png/webp MIME)
- **Max size:** `2 * 1024 * 1024` bytes to match frontend `profileImage.ts` (stricter than meal 5MB)
- **Reject:** wrong type/size with `400`/`422` field errors on `image`
- **Content-type:** Prefer extension + Django ImageField validation; do not trust client MIME alone

### 6. Profile GET/PATCH URL exposure

- **Choice:** Add read-only `profile_image_url` on extended profile payload (top-level and/or under `customer_profile` — prefer both consistency with frontend: ProfilePage reads `profile.profile_image_url` from mapped client state; ensure serializer exposes it where the frontend already looks — typically on the flattened profile object after client mapping). Implement as SerializerMethodField returning `request.build_absolute_uri(field.url)` when not already absolute (S3 URLs are absolute)
- **PATCH `profile_image_url`:** Ignore client-supplied data URLs/remote URLs for security (do not write ImageField from arbitrary strings). Treat `profile_image_url: null` as clear/delete picture to support frontend remove flow without a separate DELETE

### 7. Old file handling

- **On replace:** Before save, if `profile.profile_picture` has a name, delete that storage object (ignore missing-key errors)
- **On clear:** Delete storage object and set field null
- **On user/profile delete:** Prefer `ImageField` + CASCADE profile delete; optionally signal to delete file (Django does not always delete files on model delete — add explicit delete in service or `pre_delete` if needed)

### 8. Admin directory

- **Choice:** Replace hardcoded `None` in `get_profile_picture_url` / overview builder with the ImageField `.url` (or null)

## Risks / Trade-offs

- [Local uploads when `USE_S3_MEDIA=false`] → Mitigation: document; prod checklist requires S3 flag; tests cover storage path independently of live AWS where possible (mock storage / `@override_settings`)
- [Name-based folders collide] → Mitigation: append short `public_id` to folder slug
- [Global `file_overwrite=False` creates sibling keys] → Mitigation: delete old key explicitly; accept new storage name
- [Frontend still sends data-URL on 404 fallback] → Mitigation: implementing the endpoint removes the fallback path; ignore unsafe PATCH URL writes
- [Orphan S3 objects if DB save fails after upload] → Mitigation: assign+save in one transaction where possible; delete-on-failure best effort
- [2MB vs other media 5MB inconsistency] → Acceptable; profile UX already enforces 2MB

## Migration Plan

1. Add field + migration (nullable, no backfill)
2. Ship service, serializer, view, URL, OpenAPI helpers, docs
3. Ensure prod env: `USE_S3_MEDIA=true`, bucket/region, IAM or keys
4. Smoke-test upload → S3 console object + HTTPS URL in API
5. Rollback: remove route / revert deploy; optional leave column nullable unused; S3 objects remain until cleaned

## Open Questions

- None blocking: folder slug uses `{sanitized_name_or_email}_{public_id8}` as the collision-safe interpretation of the requested structure.
- Optional later: dedicated `DELETE .../profile/image/` if PATCH-null is insufficient for clients.
