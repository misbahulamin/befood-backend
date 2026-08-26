## Context

**Current stack (analyzed):**

| Item | Value |
| --- | --- |
| Django | 5.1.3 |
| Python | 3.12.4 |
| DRF | 3.15.2 |
| Env loading | `python-decouple` (`config()` in `base.py`) — already installed |
| Settings | `core/settings/__init__.py` selects `local.py` or `prod.py` via `DJANGO_ENV` |
| Media (all envs today) | `MEDIA_URL = "/media/"`, `MEDIA_ROOT = BASE_DIR / "media"` in `base.py` |
| Static | `STATIC_URL = "/static/"`, `STATIC_ROOT = BASE_DIR / "staticfiles"` |
| Production static | `STATICFILES_STORAGE = whitenoise.storage.CompressedManifestStaticFilesStorage` in `prod.py` |
| Media serving | `core/urls.py` mounts `static(MEDIA_URL, MEDIA_ROOT)` only when `DEBUG=True` — production does **not** serve media locally |
| S3 packages | **Not installed** — `django-storages`, `boto3` missing from `requirements.txt` |

**ImageField / FileField usage (models unchanged):**

| App | Field | `upload_to` path |
| --- | --- | --- |
| `user_management` | `avatar` | `avatars/` |
| `business` | `logo` | `business/` |
| `meals` | `meal_thumbnail` | `meals/thumbnails/<slug-timestamp>.<ext>` (via `meal_thumbnail_upload_path`) |
| `blogs` | `cover_image` | `blogs/covers/<slug-timestamp>.<ext>` |
| `announcements` | `image` | `announcements/banners/<slug-timestamp>.<ext>` |
| `promotions` | `banner_image` | `promotions/` |
| `onahar` | `image` | `onahar/distributions/%Y/%m/` |
| `inventory` | `invoice` | `inventory/invoices/{public_id}/{filename}` |

**Serializer URL handling:** `meals/api/serializers.py` and `blogs/api/serializers.py` use `field.url` + `request.build_absolute_uri()`. With S3, `.url` returns an absolute HTTPS URL; `build_absolute_uri()` on an already-absolute URL is a no-op in Django — no serializer changes needed.

**AWS resources (user-provided, not hardcoded):**

- Bucket: `befood-production-media`
- Region: `ap-south-1`

## Goals / Non-Goals

**Goals:**

- Store production media on S3 with env-based credentials
- Preserve all existing `upload_to` paths and model definitions
- Keep local filesystem media for development (`DJANGO_ENV=local`)
- Keep static files on WhiteNoise (no S3 static migration)
- Provide `migrate_media_to_s3` management command for one-time migration
- Return full S3 HTTPS URLs in API responses
- Document EC2 env setup and testing plan

**Non-Goals:**

- Migrating static files to S3 / CloudFront
- Changing models, serializers, or API endpoints
- Migrating existing DB-stored URL strings (only storage backend changes)
- Using `.env` file on EC2 production (use systemd/OS env vars)
- Adding `django-environ` or `python-dotenv` (project already uses `python-decouple`)

## Decisions

### 1. Keep `python-decouple` for environment variables

**Decision:** Extend existing `config()` usage in settings; do not add `django-environ` or `python-dotenv`.

**Rationale:** `python-decouple==3.8` is already in `requirements.txt` and used throughout `base.py`. Adding another env library creates inconsistency.

**Local dev:** `decouple` reads from `.env` in project root automatically when present.

**Production:** EC2 sets OS environment variables; `decouple` reads them directly (no `.env` file needed).

### 2. Use Django 5.1 `STORAGES` dict (not legacy `DEFAULT_FILE_STORAGE`)

**Decision:** Configure S3 only in `prod.py`:

```python
STORAGES = {
    "default": {
        "BACKEND": "core.storage.S3MediaStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
```

**Rationale:** Django 5.1 supports `STORAGES`; `prod.py` already sets `STATICFILES_STORAGE` for WhiteNoise — migrate that to `STORAGES["staticfiles"]` for consistency.

**Local:** Do not set `STORAGES` in `local.py` — Django defaults to `FileSystemStorage` using `MEDIA_ROOT`.

### 3. Thin custom storage class in `core/storage.py`

**Decision:** Subclass `storages.backends.s3.S3Storage` with production-safe defaults:

- `default_acl = "public-read"` (or bucket-policy-based public access)
- `file_overwrite = False` (prevent accidental overwrites)
- `querystring_auth = False` (return clean public URLs, not signed URLs)
- No `location` prefix — keys match existing `upload_to` paths exactly

**Alternative considered:** Raw `S3Boto3Storage` settings in `prod.py` only — rejected because a subclass centralizes behavior and is easier to test/override.

### 4. AWS settings in `base.py` (reads only), activation in `prod.py`

**Decision:** Read AWS env vars in `base.py` as optional defaults; only wire S3 storage backend in `prod.py`.

```python
# base.py — read env, no storage backend switch
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='')
AWS_S3_CUSTOM_DOMAIN = config('AWS_S3_CUSTOM_DOMAIN', default='')  # optional CDN
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
```

**Rationale:** Centralizes env var names; `prod.py` activates storage only when `DJANGO_ENV=prod`.

### 5. Static files stay on WhiteNoise

**Decision:** No S3 for static files. Update `prod.py` to use:

```python
STORAGES = {
    "default": {"BACKEND": "core.storage.S3MediaStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
```

Remove standalone `STATICFILES_STORAGE` line (superseded by `STORAGES`).

**Note:** Verify `WhiteNoiseMiddleware` is in `MIDDLEWARE` — currently only `STATICFILES_STORAGE` is set in `prod.py` but middleware may be missing. Add `whitenoise.middleware.WhiteNoiseMiddleware` after `SecurityMiddleware` if not present (required for WhiteNoise to serve static in production).

### 6. Migration command in `core/management/commands/`

**Decision:** `migrate_media_to_s3` command:

1. Walk `MEDIA_ROOT` recursively
2. For each file, compute S3 key = relative path from `MEDIA_ROOT`
3. Check existence via `boto3` `head_object` — skip if exists
4. Upload with `upload_file`
5. Print progress (`uploaded`, `skipped`, `failed` counts)
6. Support `--dry-run` flag

Place in `core/` (cross-cutting infrastructure, not app-specific).

### 7. Optional local S3 testing via env flag

**Decision:** Add `USE_S3_MEDIA=config('USE_S3_MEDIA', default=False, cast=bool)` — when `True` in `local.py`, enable same `STORAGES` config for integration testing against a dev bucket.

**Rationale:** Allows verifying S3 uploads locally without setting `DJANGO_ENV=prod`.

### 8. S3 bucket configuration (AWS console — not code)

Required AWS setup (user already created bucket):

- **Bucket:** `befood-production-media`, region `ap-south-1`
- **Block Public Access:** Disable for public media OR use bucket policy for `s3:GetObject` on `arn:aws:s3:::befood-production-media/*`
- **CORS:** Allow `GET` from `https://befood.com.bd`, `https://api.befood.com.bd`, `http://localhost:5173`
- **IAM user/role:** Programmatic access with `s3:PutObject`, `s3:GetObject`, `s3:ListBucket`, `s3:HeadObject` on the bucket

**Preferred production auth:** EC2 instance IAM role (no access keys on server). If using IAM role, omit `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` — boto3 picks up instance metadata automatically. Keep env vars optional in that case.

## Files to Modify

| File | Change | Reason |
| --- | --- | --- |
| `requirements.txt` | Add `django-storages`, `boto3` | S3 backend dependencies |
| `.env.example` | Add AWS variable placeholders | Document required env vars for developers |
| `.gitignore` | Verify `.env` present (already is) | Protect secrets |
| `core/settings/base.py` | Add `storages` to `INSTALLED_APPS`; read AWS env vars | Shared config loading |
| `core/settings/prod.py` | Set `STORAGES` for S3 media + WhiteNoise static; remove legacy `STATICFILES_STORAGE` | Activate S3 in production only |
| `core/settings/local.py` | Optional `USE_S3_MEDIA` override; no change to default local media | Dev convenience |
| `core/storage.py` | **New** — `S3MediaStorage` subclass | Centralized S3 behavior |
| `core/management/commands/migrate_media_to_s3.py` | **New** — migration command | One-time local→S3 upload |
| `core/tests/test_s3_storage.py` | **New** — config and command tests | Verify settings and migration logic |

**Files NOT modified:** All model files, serializers, API views, URLs (except potential WhiteNoise middleware addition in `base.py` or `prod.py`).

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| Existing production media on EC2 disk becomes inaccessible after S3 switch | Run `migrate_media_to_s3` before/after deploy; keep EC2 disk backup until verified |
| Public bucket exposes all media | Acceptable for product images; invoices in `inventory/invoices/` may need `private` ACL + signed URLs in future — out of scope now |
| `build_absolute_uri` on S3 URL edge cases | Django handles absolute URLs correctly; add test |
| Missing WhiteNoise middleware | Verify and add during implementation |
| Hardcoded DB credentials in `local.py`/`prod.py` (pre-existing) | Out of scope for this change; recommend separate cleanup to use `config()` |
| IAM keys on EC2 vs instance role | Document both approaches; prefer IAM role |

## Migration Plan

### Phase 1 — Code deploy (no storage switch yet)

1. Merge S3 storage code with feature behind `DJANGO_ENV=prod` only
2. Install packages on EC2: `pip install django-storages boto3`
3. Set env vars on EC2 (see below)

### Phase 2 — Migrate existing files

```bash
# On EC2, before switching DJANGO_ENV or after with local MEDIA_ROOT still populated
python manage.py migrate_media_to_s3 --dry-run   # preview
python manage.py migrate_media_to_s3              # upload
```

### Phase 3 — Activate S3 storage

1. Deploy updated `prod.py` with `STORAGES` config
2. Restart gunicorn/systemd service
3. Verify new uploads go to S3
4. Verify API returns S3 URLs

### Rollback

1. Revert `prod.py` `STORAGES` to filesystem (remove S3 backend)
2. Restart service — new uploads go to local disk again
3. S3 files remain (no data loss)

## Environment Variable Setup

### `.env` (local development — never commit)

```env
AWS_ACCESS_KEY_ID=your-dev-or-prod-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=befood-production-media
AWS_S3_REGION_NAME=ap-south-1
# Optional: test S3 locally without prod settings
USE_S3_MEDIA=false
```

### `.env.example` (committed — empty placeholders)

```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=
USE_S3_MEDIA=false
```

### EC2 production (systemd — recommended)

```ini
# /etc/systemd/system/befood-gunicorn.service.d/aws.conf
[Service]
Environment="AWS_ACCESS_KEY_ID=AKIA..."
Environment="AWS_SECRET_ACCESS_KEY=..."
Environment="AWS_STORAGE_BUCKET_NAME=befood-production-media"
Environment="AWS_S3_REGION_NAME=ap-south-1"
Environment="DJANGO_ENV=prod"
```

Then: `sudo systemctl daemon-reload && sudo systemctl restart befood-gunicorn`

**Alternative:** `/etc/environment` or shell profile — less ideal for service isolation.

**Best practice:** Attach IAM role to EC2 instance with S3 bucket policy — no keys on server.

## Testing Plan

| # | Test | Steps | Expected |
| --- | --- | --- | --- |
| 1 | Django shell upload | `DJANGO_ENV=prod` + AWS vars; create model with ImageField, assign file, save | File in S3; `.url` is `https://...s3.ap-south-1.amazonaws.com/...` |
| 2 | Admin upload | Upload meal thumbnail, avatar, announcement banner via admin | Files visible in S3 console under correct paths |
| 3 | API response | `GET /meals/` or `/blogs/` | Image fields return full S3 HTTPS URLs |
| 4 | Browser | Open S3 URL directly | Image loads; no 403; CORS OK for frontend |
| 5 | Migration command | `migrate_media_to_s3 --dry-run` then real run | Local files uploaded; re-run skips existing |
| 6 | Production EC2 | Deploy + restart; upload new image | S3 object created; old local files still accessible via migrated URLs |

## Security Checklist

- [ ] No AWS keys in any `.py` file
- [ ] `.env` in `.gitignore` (already present)
- [ ] `.env.example` has empty placeholders only
- [ ] `git status` does not show `.env`
- [ ] IAM permissions follow least privilege
- [ ] Pre-existing hardcoded email/DB passwords in settings flagged for future cleanup (not introduced by this change)

## Open Questions

1. **IAM role vs access keys on EC2** — Does the EC2 instance already have an IAM role with S3 access? If yes, skip key env vars.
2. **Invoice files (`inventory/invoices/`)** — Should these be private with signed URLs? Current spec assumes public-read like images.
3. **WhiteNoise middleware** — Confirm current production deployment serves static correctly; add middleware if missing.
