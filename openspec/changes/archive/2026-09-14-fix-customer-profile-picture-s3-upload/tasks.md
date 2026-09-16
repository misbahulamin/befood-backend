## 1. Model & migration

- [x] 1.1 Add nullable `profile_picture` ImageField on `CustomerProfile` with `upload_to` pointing at the profile-picture path helper
- [x] 1.2 Generate and apply migration for the new field

## 2. Path, validation & service layer

- [x] 2.1 Implement folder-slug helpers (name → sanitize; else email local-part; append short `public_id`) and `profiles/users/{slug}/profile_picture.{ext}` upload path
- [x] 2.2 Implement image validation (jpg/jpeg/png/webp, max 2 MiB) mirroring meal/announcement helpers
- [x] 2.3 Implement `upload_profile_picture(profile, file)` service: validate, delete previous storage object, save field, return absolute media URL
- [x] 2.4 Implement `clear_profile_picture(profile)` for remove/null flow with storage delete

## 3. Customer API

- [x] 3.1 Add upload serializer accepting multipart field `image`
- [x] 3.2 Add `CustomerProfileImageUploadView` (`HasCustomerProfile`) at `customer/profile/image/`
- [x] 3.3 Expose nullable `profile_image_url` on extended profile GET/PATCH responses
- [x] 3.4 On profile PATCH: ignore data/remote URL writes for `profile_image_url`; treat `null` as clear via service
- [x] 3.5 Register URL + OpenAPI/`extend_schema` for the upload endpoint

## 4. Admin customer directory

- [x] 4.1 Replace hardcoded `None` in list serializer `get_profile_picture_url` with stored field URL or null
- [x] 4.2 Replace hardcoded `profile_picture_url: None` in overview builder with stored field URL or null
- [x] 4.3 Update admin customer backend/frontend docs that currently say picture is always null

## 5. Documentation

- [x] 5.1 Add `user_management/docs/frontend/customer-profile-picture.md` (endpoint, FormData field, response, errors, auth)
- [x] 5.2 Add `user_management/docs/backend/customer-profile-picture.md` (model, path rules, S3/`USE_S3_MEDIA`, replace/clear)
- [x] 5.3 Note prod requirement: `USE_S3_MEDIA=true` + AWS bucket/region (and IAM/keys) for S3 persistence

## 6. Tests

- [x] 6.1 Unit tests for slug/path generation (named user, email-only user, collision-safe public_id suffix)
- [x] 6.2 API test: authenticated customer upload success updates DB field and returns `profile_image_url`
- [x] 6.3 API tests: unauthenticated `401`; invalid type rejected; oversized rejected
- [x] 6.4 API test: replace deletes/replaces previous file reference; clear via `profile_image_url: null`
- [x] 6.5 Assert object key prefix `profiles/users/` and filename `profile_picture.*` (use temporary/local storage or mocked storage)
- [x] 6.6 Admin list/overview returns non-null `profile_picture_url` when picture exists
- [x] 6.7 Manual/smoke checklist when `USE_S3_MEDIA=true`: upload → object visible in S3 → HTTPS URL loads (document result in change notes if run)

## 7. Verification

- [x] 7.1 Run targeted pytest modules for profile picture + admin customer picture URL
- [x] 7.2 Confirm frontend contract unchanged (`POST .../profile/image/`, field `image`, response `profile_image_url`)
