## Why

The Befood backend currently stores all uploaded media (meal thumbnails, avatars, blog covers, announcement banners, invoices, etc.) on the EC2 instance's local filesystem (`MEDIA_ROOT`). This is fragile for production: disk space is limited, files are lost on instance replacement, and media is not served when `DEBUG=False` (no `static()` URL mount in production). Moving media to AWS S3 provides durable, scalable object storage with direct HTTPS URLs, aligning with the existing EC2 + RDS deployment on `ap-south-1`.

## What Changes

- Add `django-storages` and `boto3` dependencies; extend existing `python-decouple` env loading (no new env library).
- Add AWS S3 environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`) to `.env.example`; document EC2 production env setup.
- Configure Django 5.1 `STORAGES` backend for **media files only** in production (`prod.py`); keep local filesystem media in `local.py` for developer convenience.
- Keep static files on WhiteNoise (`STATICFILES_STORAGE` in `prod.py`) — no S3 static migration unless explicitly needed later.
- Add `core/storage.py` with a thin `S3MediaStorage` subclass preserving existing `upload_to` paths unchanged.
- Add `core/management/commands/migrate_media_to_s3.py` to safely upload existing local `media/` files to S3 without duplication.
- Image/File field API responses return full S3 HTTPS URLs (e.g. `https://<bucket>.s3.<region>.amazonaws.com/meals/thumbnails/...`) instead of `/media/...` paths — no model or serializer contract changes required beyond URL format.
- Add tests for storage configuration and migration command.

No model migrations. No API endpoint changes. No breaking serializer field changes. **Behavioral (additive):** media URLs become absolute S3 URLs in production instead of relative `/media/` paths.

## Capabilities

### New Capabilities

- `aws-s3-media-storage`: Production media file storage on AWS S3 with env-based credentials, preserved `upload_to` paths, local-dev fallback, and a safe migration command for existing files.

### Modified Capabilities

_(none — URL format change is an implementation detail; existing specs for blog, meal, announcement, and inventory feeds remain valid with absolute URLs)_

## Impact

| Area | Files / systems |
| --- | --- |
| Dependencies | `requirements.txt` — add `django-storages`, `boto3` |
| Settings | `core/settings/base.py` (shared AWS env reads), `core/settings/prod.py` (S3 `STORAGES`), `core/settings/local.py` (explicit local media, optional S3 override for testing) |
| Storage backend | `core/storage.py` (new) |
| Management command | `core/management/commands/migrate_media_to_s3.py` (new) |
| Environment | `.env.example`, `.gitignore` (verify `.env` ignored) |
| Deployment | EC2 environment variables, IAM/S3 bucket policy on `befood-production-media` |
| Existing models | No changes — `ImageField`/`FileField` with existing `upload_to` paths continue working |
| Serializers | No changes required — `field.url` and `build_absolute_uri` work with S3 absolute URLs |
| Static files | Unchanged — WhiteNoise in production |
| Tests | New storage/migration tests; existing media tests may need `override_settings` for local storage |

**Upload paths in use (must be preserved on S3):**

- `avatars/` — user profiles
- `business/` — business logos
- `meals/thumbnails/` — meal images (dynamic filename)
- `blogs/covers/` — blog cover images
- `announcements/banners/` — announcement banners
- `promotions/` — promotion banners
- `onahar/distributions/%Y/%m/` — onahar distribution photos
- `inventory/invoices/{public_id}/` — inventory invoice PDFs
